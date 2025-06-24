/* global gradioApp, onUiUpdate, onAfterUiUpdate */

// --- Start of Custom Tag Weighting (CTW) specific JavaScript ---

const CTW_PROMPT_TEXTAREA_IDS = [
    "txt2img_prompt",
    "txt2img_neg_prompt",
    "img2img_prompt",
    "img2img_neg_prompt",
    // Standard A1111 IDs for Hires Fix prompts (these are component IDs, textarea is inside)
    "txt2img_hr_prompt",
    "txt2img_hr_negative_prompt"
    // Add other known prompt component IDs if necessary (e.g., for inpainting)
];

let ctwActiveTextarea = null; // Store the textarea being modified

function ctwGetTagWeightRequestPayload(textarea, direction) {
    return JSON.stringify({
        prompt_text: textarea.value,
        cursor_pos_start: textarea.selectionStart,
        cursor_pos_end: textarea.selectionEnd, // Keep for potential future use with selections
        direction: direction,
        // weight_step: 0.1 // Python side defaults this
    });
}

function ctwHandleCtrlWeight(event) {
    // console.log("CTW: ctwHandleCtrlWeight triggered for key:", event.key, "Ctrl:", event.ctrlKey, "Meta:", event.metaKey);

    if (!((event.ctrlKey || event.metaKey) && (event.key === 'ArrowUp' || event.key === 'ArrowDown'))) {
        return;
    }

    const textarea = event.target;
    // Ensure this is one of the textareas we explicitly attached a listener to
    if (!textarea.dataset.ctwKeydownAttached) {
        // console.log("CTW: Event on textarea without ctwKeydownAttached dataset. Ignoring.", textarea);
        return;
    }

    console.log(`CTW: Event Ctrl+${event.key} on target textarea:`, textarea.id || `(no id, placeholder: "${textarea.placeholder || 'N/A'}")`);
    event.preventDefault();
    event.stopPropagation();

    ctwActiveTextarea = textarea;
    const direction = event.key === 'ArrowUp' ? 'up' : 'down';
    const payload = ctwGetTagWeightRequestPayload(textarea, direction);
    console.log("CTW: Payload prepared:", payload);

    // Corrected elem_ids to match those defined in custom_tag_weighting.py
    const reqTextbox = gradioApp().querySelector("#ctw-tag_weight_req_textbox textarea");
    const actionButton = gradioApp().querySelector("#ctw-apply_tag_weight_action_button");

    if (!reqTextbox) {
        console.error("CTW: Request Textbox (#ctw-tag_weight_req_textbox textarea) not found.");
        ctwActiveTextarea = null;
        return;
    }
    if (!actionButton) {
        console.error("CTW: Action Button (#ctw-apply_tag_weight_action_button) not found.");
        ctwActiveTextarea = null;
        return;
    }
    console.log("CTW: Gradio request textbox and action button found.");

    reqTextbox.value = payload;
    const inputEvent = new Event('input', { bubbles: true }); // Must be dispatched on the textarea itself
    reqTextbox.dispatchEvent(inputEvent);
    console.log("CTW: Set request textbox value, dispatched input event.");

    actionButton.click();
    console.log("CTW: Clicked action button. Waiting for response...");
}

function ctwSetupTagWeightResponseHandler() {
    const resTextbox = gradioApp().querySelector("#ctw-tag_weight_res_textbox textarea");

    if (!resTextbox) {
        console.warn("CTW: Response Textbox (#ctw-tag_weight_res_textbox textarea) not found yet. Will retry on next UI update.");
        return false;
    }

    if (resTextbox.dataset.ctwObserverAttached === 'true') {
        return true;
    }

    console.log("CTW: Found response textbox. Setting up MutationObserver:", resTextbox);

    const observer = new MutationObserver((mutationsList, observerInstance) => {
        if (!ctwActiveTextarea) {
            return;
        }
        console.log("CTW: MutationObserver fired for response textbox. Active textarea:", ctwActiveTextarea.id || `(no id, placeholder: "${ctwActiveTextarea.placeholder || 'N/A'}")`);

        for(const mutation of mutationsList) {
            if (mutation.type === 'childList' || mutation.type === 'characterData' || mutation.type === 'attributes') {
                const responseJson = resTextbox.value;
                console.log("CTW: Response textbox value:", responseJson);

                if (responseJson && responseJson.trim() !== "") {
                    try {
                        const response = JSON.parse(responseJson);
                        console.log("CTW: Parsed response:", response);

                        if (response.success && response.new_prompt_text !== undefined) {
                            console.log("CTW: Success. Updating textarea with new prompt:", response.new_prompt_text);
                            const oldScrollTop = ctwActiveTextarea.scrollTop;
                            const oldSelectionStart = ctwActiveTextarea.selectionStart;
                            const oldText = ctwActiveTextarea.value;
                            const changeInLength = response.new_prompt_text.length - oldText.length;

                            ctwActiveTextarea.value = response.new_prompt_text;

                            const newCursorPos = Math.max(0, oldSelectionStart + changeInLength);

                            ctwActiveTextarea.selectionStart = newCursorPos;
                            ctwActiveTextarea.selectionEnd = newCursorPos;
                            ctwActiveTextarea.scrollTop = oldScrollTop;
                            console.log("CTW: Textarea updated. New cursor pos:", newCursorPos);

                            if (window.updateInput) {
                                window.updateInput(ctwActiveTextarea);
                                console.log("CTW: Called window.updateInput().");
                            } else {
                                const inputEvent = new Event('input', { bubbles: true });
                                ctwActiveTextarea.dispatchEvent(inputEvent);
                                console.log("CTW: Dispatched input event as fallback.");
                            }

                        } else if (response.error) {
                            console.warn("CTW Error from Python: " + response.error);
                        } else {
                            console.warn("CTW: Response not successful or new_prompt_text missing.", response);
                        }
                    } catch (e) {
                        console.error("CTW: Failed to parse response JSON.", e, "JSON was:", responseJson);
                    }

                    resTextbox.value = "";
                    const clearEvent = new Event('input', { bubbles: true });
                    resTextbox.dispatchEvent(clearEvent);
                    // console.log("CTW: Cleared response textbox."); // Reduced verbosity

                    ctwActiveTextarea = null;
                    // console.log("CTW: Reset active textarea."); // Reduced verbosity
                    break;
                }
            }
        }
    });

    observer.observe(resTextbox, { childList: true, characterData: true, subtree: true, attributes: true, attributeOldValue: true });
    resTextbox.dataset.ctwObserverAttached = 'true';
    console.log("CTW: Response handler (MutationObserver) successfully set up and observing for:", resTextbox);
    return true;
}

function ctwAttachKeydownListeners() {
    // console.log("CTW: Attempting to find and attach to prompt textareas...");
    let actuallyAttachedCount = 0;

    CTW_PROMPT_TEXTAREA_IDS.forEach(idFragment => {
        const container = gradioApp().querySelector(`#${idFragment}`);
        if (container) {
            let textarea = (container.tagName === 'TEXTAREA') ? container : container.querySelector("textarea");
            if (textarea) {
                if (!textarea.dataset.ctwKeydownAttached) {
                    textarea.addEventListener('keydown', ctwHandleCtrlWeight);
                    textarea.dataset.ctwKeydownAttached = true;
                    console.log(`CTW: Attached keydown listener to textarea in #${idFragment} (ID: ${textarea.id || 'N/A'}, Placeholder: "${textarea.placeholder || 'N/A'}")`);
                    actuallyAttachedCount++;
                }
            } else {
                 // console.warn(`CTW: Textarea not found within #${idFragment}`);
            }
        } else {
             // console.warn(`CTW: Container element #${idFragment} not found for main prompts.`);
        }
    });

    if (actuallyAttachedCount > 0) {
        // console.log(`CTW: Successfully attached/verified keydown listeners for ${actuallyAttachedCount} targeted textareas.`);
    } else {
        // console.warn("CTW: Could not find or attach to any of the primary prompt textareas using current selectors during this call. Will retry on UI update.");
    }
}

// Standard A1111 UI update hook
(
  window.onAfterUiUpdate || window.onUiUpdate || (() => {}) // Fallback to empty function if neither exists
)(() => {
  // console.log("CTW: onUiUpdate triggered.");
  ctwAttachKeydownListeners();
  if (!window.ctwTagWeightResponseHandlerAttached) {
    if (ctwSetupTagWeightResponseHandler()) {
        window.ctwTagWeightResponseHandlerAttached = true;
        console.log("CTW: Tag Weight Response Handler global flag set to true.");
    }
  }
});

console.log("Custom Tag Weighting (CTW) JavaScript loaded.");
// --- End of Custom Tag Weighting (CTW) specific JavaScript ---
