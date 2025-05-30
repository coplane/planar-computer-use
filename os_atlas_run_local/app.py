import gradio as gr
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import base64
from PIL import ImageDraw
from io import BytesIO
import re


models = {
    "OS-Copilot/OS-Atlas-Base-7B": Qwen2VLForConditionalGeneration.from_pretrained("OS-Copilot/OS-Atlas-Base-7B", torch_dtype="auto", device_map="auto"),
}

processors = {
    "OS-Copilot/OS-Atlas-Base-7B": AutoProcessor.from_pretrained("OS-Copilot/OS-Atlas-Base-7B")
}


def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str


def draw_bounding_boxes(image, bounding_boxes, outline_color="red", line_width=2):
    draw = ImageDraw.Draw(image)
    for box in bounding_boxes:
        xmin, ymin, xmax, ymax = box
        draw.rectangle([xmin, ymin, xmax, ymax], outline=outline_color, width=line_width)
    return image


def rescale_bounding_boxes(bounding_boxes, original_width, original_height, scaled_width=1000, scaled_height=1000):
    x_scale = original_width / scaled_width
    y_scale = original_height / scaled_height
    rescaled_boxes = []
    for box in bounding_boxes:
        xmin, ymin, xmax, ymax = box
        rescaled_box = [
            xmin * x_scale,
            ymin * y_scale,
            xmax * x_scale,
            ymax * y_scale
        ]
        rescaled_boxes.append(rescaled_box)
    return rescaled_boxes


# Patterns to extract the main parts
object_ref_pattern = r"<\|object_ref_start\|>(.*?)<\|object_ref_end\|>"
box_pattern = r"<\|box_start\|>(.*?)<\|box_end\|>"

def parse_bounding_box_info(text):
    """
    Extracts object reference and bounding box coordinates from a given text.
    Handles coordinates in formats like (x1,y1),(x2,y2) or [[x1,y1,x2,y2]].
    """
    object_ref_match = re.search(object_ref_pattern, text)
    box_match = re.search(box_pattern, text)

    object_ref = None
    if object_ref_match:
        object_ref = object_ref_match.group(1)
    else:
        print(f"Warning: Object reference not found in text: {text[:50]}...")
        # Depending on requirements, you might want to raise an error or return early

    extracted_boxes = [] # Will hold the final [[x1, y1, x2, y2]] structure

    if box_match:
        box_content = box_match.group(1).strip() # .strip() to handle leading/trailing spaces

        # Universal way to find all numbers (integers, possibly negative)
        # This will extract numbers from "(49,579),(142,701)" as ['49', '579', '142', '701']
        # and from "[[0, 399, 219, 562]]" as ['0', '399', '219', '562']
        # It's robust to spaces around commas or brackets.
        numbers_str = re.findall(r'-?\d+', box_content)

        if len(numbers_str) == 4:
            try:
                # Convert all found numbers to integers
                coords = [int(n) for n in numbers_str]
                # The problem asks for the format [[x1, y1, x2, y2]]
                extracted_boxes = [coords]
            except ValueError:
                print(f"Warning: Could not convert all extracted numbers to integers in box_content: '{box_content}'")
        elif numbers_str: # If some numbers were found, but not 4
            print(f"Warning: Expected 4 coordinates in box_content, but found {len(numbers_str)}: '{box_content}'")
        # else: # No numbers found, or box_content was empty
            # print(f"Warning: No numbers found in box_content: '{box_content}'")
    else:
        # Handle cases where <|box_start|>...<|box_end|> is not present
        print(f"Warning: Box content not found in text: {text[:50]}...")
        pass # extracted_boxes remains empty

    return object_ref, extracted_boxes


def run_example(image, text_input, model_id="OS-Copilot/OS-Atlas-Base-7B"):
    model = models[model_id].eval()
    processor = processors[model_id]
    prompt = f"In this UI screenshot, what is the position of the element corresponding to the command \"{text_input}\" (with bbox)?"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"data:image;base64,{image_to_base64(image)}"},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("mps")

    generated_ids = model.generate(**inputs, max_new_tokens=128)
    generated_ids_trimmed = [
        out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    print(output_text)
    text = output_text[0]

    object_ref, boxes = parse_bounding_box_info(text)

    scaled_boxes = rescale_bounding_boxes(boxes, image.width, image.height)
    return object_ref, scaled_boxes, draw_bounding_boxes(image, scaled_boxes)

css = """
  #output {
    height: 500px; 
    overflow: auto; 
    border: 1px solid #ccc; 
  }
"""
with gr.Blocks(css=css) as demo:
    gr.Markdown(
    """
    # Demo for OS-ATLAS: A Foundation Action Model For Generalist GUI Agents
    """)
    with gr.Row():
        with gr.Column():
            input_img = gr.Image(label="Input Image", type="pil")
            model_selector = gr.Dropdown(choices=list(models.keys()), label="Model", value="OS-Copilot/OS-Atlas-Base-7B")
            text_input = gr.Textbox(label="User Prompt")
            submit_btn = gr.Button(value="Submit")
        with gr.Column():
            model_output_text = gr.Textbox(label="Model Output Text")
            model_output_box = gr.Textbox(label="Model Output Box")
            annotated_image = gr.Image(label="Annotated Image")

    # gr.Examples(
    #     examples=[
    #         ["assets/web_6f93090a-81f6-489e-bb35-1a2838b18c01.png", "select search textfield"],
    #         ["assets/web_6f93090a-81f6-489e-bb35-1a2838b18c01.png", "switch to discussions"],
    #     ],
    #     inputs=[input_img, text_input],
    #     outputs=[model_output_text, model_output_box, annotated_image],
    #     fn=run_example,
    #     cache_examples=True,
    #     label="Try examples"
    # )

    submit_btn.click(run_example, [input_img, text_input, model_selector], [model_output_text, model_output_box, annotated_image])

demo.launch(debug=True, server_name="0.0.0.0", server_port=7080)
