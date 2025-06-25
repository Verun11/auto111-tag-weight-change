import gradio as gr
import modules.scripts as scripts
import json
import logging

# Attempt to import from the new local package structure
try:
    from sd_custom_tag_weighting.tag_utils import get_tag_at_cursor, apply_weight_to_tag, ignore_initial_tags
except ImportError:
    # Fallback for development or if Python path isn't immediately updated
    # This assumes tag_utils.py might be temporarily in a place Python can find directly
    # or that this script is run from a context where sd_custom_tag_weighting is not yet in sys.path.
    # For a proper extension structure, the `from sd_custom_tag_weighting...` should work.
    try:
        from ..sd_custom_tag_weighting.tag_utils import get_tag_at_cursor, apply_weight_to_tag, ignore_initial_tags
        print("CustomTagWeighting: Used relative import for tag_utils.")
    except ImportError:
        # This is a critical failure if tag_utils cannot be imported.
        # For now, define stubs so the class can be defined, but it won't work.
        def get_tag_at_cursor(prompt_text: str, cursor_pos: int) -> tuple[str | None, int, int]: return None, -1, -1
        def apply_weight_to_tag(*args, **kwargs) -> str: return args[0] if args else ""
        def ignore_initial_tags(prompt_text: str, num_to_ignore: int) -> str: return prompt_text # Stub
        print("CustomTagWeighting: CRITICAL - tag_utils.py not found. Functions will be stubbed.")


EXTENSION_NAME = "Custom Tag Weighting"
EXTENSION_VERSION = "1.0.0"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Or logging.DEBUG for more verbose logs from this extension

def make_ctw_element_id(name: str) -> str:
    """Helper to create unique element IDs for this extension."""
    return f"ctw-{name}"

class CustomTagWeightingScript(scripts.Script):
    def title(self):
        return f"{EXTENSION_NAME} v{EXTENSION_VERSION}"

    def show(self, is_img2img):
        # This script is always active via JavaScript, but doesn't need a visible UI in the A1111 script dropdown.
        # However, to register its Gradio components for JS to use, it might need to be AlwaysVisible initially,
        # or its components added in a different way (e.g. via shared.py hooks if available for adding components).
        # For simplicity of having a .py script recognized, AlwaysVisible is common.
        # The actual UI elements we add will be hidden.
        return scripts.AlwaysVisible

    def process_tag_weight_request(self, request_json_str: str):
        try:
            logger.debug(f"{EXTENSION_NAME}: Processing tag weight request: {request_json_str}")
            data = json.loads(request_json_str)
            prompt_text = data.get("prompt_text")
            cursor_pos = data.get("cursor_pos_start")
            direction = data.get("direction")
            weight_step = float(data.get("weight_step", 0.1))

            if prompt_text is None or cursor_pos is None or direction is None:
                logger.error(f"{EXTENSION_NAME}: Tag weight request missing parameters.")
                response_json = json.dumps({"success": False, "error": "Missing parameters", "new_prompt_text": prompt_text if prompt_text is not None else ""})
                logger.debug(f"{EXTENSION_NAME}: Returning to JS: {response_json}")
                return response_json

            tag_info = get_tag_at_cursor(prompt_text, cursor_pos)

            if tag_info and tag_info[0] is not None:
                stripped_tag, raw_start, raw_end = tag_info

                new_prompt_text = apply_weight_to_tag(
                    prompt_text,
                    stripped_tag,
                    raw_start,
                    raw_end,
                    direction,
                    weight_step=weight_step
                )
                logger.debug(f"{EXTENSION_NAME}: Tag weighting applied. Original: '{prompt_text}', New: '{new_prompt_text}'")
                response_json = json.dumps({"success": True, "new_prompt_text": new_prompt_text})
                logger.debug(f"{EXTENSION_NAME}: Returning to JS: {response_json}")
                return response_json
            else:
                logger.debug(f"{EXTENSION_NAME}: No tag found at cursor position {cursor_pos} in prompt '{prompt_text}'")
                response_json = json.dumps({"success": False, "error": "No tag found at cursor position", "new_prompt_text": prompt_text})
                logger.debug(f"{EXTENSION_NAME}: Returning to JS: {response_json}")
                return response_json

        except Exception as e:
            logger.error(f"{EXTENSION_NAME}: Error processing tag weight request: {e}", exc_info=True)
            error_return_prompt = ""
            if isinstance(request_json_str, str):
                try:
                    data_for_error = json.loads(request_json_str)
                    error_return_prompt = data_for_error.get("prompt_text", "")
                except json.JSONDecodeError:
                    logger.warn(f"{EXTENSION_NAME}: Could not parse request_json_str in error handler: {request_json_str}")

            response_json = json.dumps({"success": False, "error": str(e), "new_prompt_text": error_return_prompt})
            logger.debug(f"{EXTENSION_NAME}: Returning error to JS: {response_json}")
            return response_json

    def ui(self, is_img2img):
        with gr.Accordion(f"{EXTENSION_NAME} Settings", open=True, visible=True, elem_id=make_ctw_element_id("accordion")):
            ignore_tags_slider = gr.Slider(
                minimum=0,
                maximum=90,
                step=1,
                label="Number of initial tags to ignore",
                value=0,
                elem_id=make_ctw_element_id("ignore_tags_slider")
            )
            gr.Markdown("---") # Separator
            gr.Markdown("Internal components for Ctrl+Up/Down tag weighting (normally hidden):")
            # The elem_id for Textbox should be on the Textbox itself, not a wrapper if querySelector targets textarea directly in JS.
            # Gradio typically creates a div with id, and textarea is inside.
            # JS will use: `gradioApp().querySelector("#ctw_tag_weight_req_textbox textarea")`
            ctw_tag_weight_req = gr.Textbox(label="Tag Weight Request Payload (Internal)", elem_id=make_ctw_element_id("tag_weight_req_textbox"), visible=False) # Keep these hidden unless debugging
            ctw_tag_weight_res = gr.Textbox(label="Tag Weight Response Payload (Internal)", elem_id=make_ctw_element_id("tag_weight_res_textbox"), visible=False) # Keep these hidden unless debugging
            ctw_apply_tag_weight_button = gr.Button("Apply Tag Weight Internal Trigger (Internal)", elem_id=make_ctw_element_id("apply_tag_weight_action_button"), visible=False) # Keep these hidden unless debugging

        ctw_apply_tag_weight_button.click(
            fn=self.process_tag_weight_request,
            inputs=[ctw_tag_weight_req],
            outputs=[ctw_tag_weight_res]
        )

        # Return all UI components that this script defines.
        # The order should match the `args` in the `process` method if we add one.
        return [ignore_tags_slider, ctw_tag_weight_req, ctw_tag_weight_res, ctw_apply_tag_weight_button]

    def process(self, p, ignore_tags_slider_val, ctw_tag_weight_req_val, ctw_tag_weight_res_val, ctw_apply_tag_weight_button_val):
        """
        This method is called before processing the prompt for image generation.
        'p' is the processing object (StableDiffusionProcessingTxt2Img or StableDiffusionProcessingImg2Img).
        The other arguments are the current values of the UI components returned by ui() in order.
        """
        num_to_ignore = int(ignore_tags_slider_val)

        if num_to_ignore > 0:
            logger.info(f"{EXTENSION_NAME}: Initial prompt: '{p.prompt}'")
            logger.info(f"{EXTENSION_NAME}: Ignoring first {num_to_ignore} tags.")

            modified_prompt = ignore_initial_tags(p.prompt, num_to_ignore)
            p.prompt = modified_prompt
            logger.info(f"{EXTENSION_NAME}: Modified prompt: '{p.prompt}'")

            # Also process negative prompt if it exists and is not empty
            if hasattr(p, 'negative_prompt') and p.negative_prompt:
                logger.info(f"{EXTENSION_NAME}: Initial negative_prompt: '{p.negative_prompt}'")
                modified_negative_prompt = ignore_initial_tags(p.negative_prompt, num_to_ignore)
                p.negative_prompt = modified_negative_prompt
                logger.info(f"{EXTENSION_NAME}: Modified negative_prompt: '{p.negative_prompt}'")

        # Ensure other prompts in the batch are also processed if applicable
        # (Although this script is likely to run once per batch for p.prompt)
        # For batch processing (p.all_prompts), this logic might need adjustment
        # if each prompt in a batch should have tags ignored independently.
        # Current A1111 script processing usually modifies p.prompt, p.negative_prompt,
        # and these are then used to generate p.all_prompts, p.all_negative_prompts.
        # So modifying p.prompt should be sufficient.

    # The `postprocess` method is not needed for this extension.
