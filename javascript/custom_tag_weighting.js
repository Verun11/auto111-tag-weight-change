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
let ctwReqTextboxEl = null;
let ctwResTextboxEl = null;
let ctwActionButtonEl = null;

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
    // console.log("CTW: Payload prepared:", payload); // Reduced verbosity

    // Use cached elements if available
    if (!ctwReqTextboxEl || !ctwActionButtonEl) {
        console.error("CTW: Request/Action Gradio elements not cached. Attempting to find them now.");
        // Attempt to find them now, this serves as a fallback if onUiUpdate hasn't run/found them yet.
        ctwReqTextboxEl = gradioApp().querySelector("#ctw-tag_weight_req_textbox textarea");
        ctwActionButtonEl = gradioApp().querySelector("#ctw-apply_tag_weight_action_button");
        if (!ctwReqTextboxEl || !ctwActionButtonEl) {
            console.error("CTW: Critical - Request/Action Gradio elements not found even on immediate attempt.");
            ctwActiveTextarea = null;
            return;
        }
    }

    // console.log("CTW: Gradio request textbox and action button available."); // Reduced verbosity

    ctwReqTextboxEl.value = payload;
    const inputEvent = new Event('input', { bubbles: true }); // Must be dispatched on the textarea itself
    ctwReqTextboxEl.dispatchEvent(inputEvent);
    // console.log("CTW: Set request textbox value, dispatched input event."); // Reduced verbosity

    ctwActionButtonEl.click();
    // console.log("CTW: Clicked action button. Waiting for response..."); // Reduced verbosity
}


function ctwInitializeGradioElements() {
    if (!ctwReqTextboxEl) {
        ctwReqTextboxEl = gradioApp().querySelector("#ctw-tag_weight_req_textbox textarea");
        if (ctwReqTextboxEl) console.log("CTW: Cached Request Textbox element.");
        else console.warn("CTW: Request Textbox element not found for caching.");
    }
    if (!ctwActionButtonEl) {
        ctwActionButtonEl = gradioApp().querySelector("#ctw-apply_tag_weight_action_button");
        if (ctwActionButtonEl) console.log("CTW: Cached Action Button element.");
        else console.warn("CTW: Action Button element not found for caching.");
    }
    if (!ctwResTextboxEl) {
        ctwResTextboxEl = gradioApp().querySelector("#ctw-tag_weight_res_textbox textarea");
        if (ctwResTextboxEl) console.log("CTW: Cached Response Textbox element.");
        else console.warn("CTW: Response Textbox element not found for caching.");
    }

    // Return true if all essential elements for response handling are cached
    return ctwResTextboxEl !== null;
}


function ctwSetupTagWeightResponseHandler() {
    if (!ctwResTextboxEl) { // Check if cached element is available
        console.warn("CTW: Response Textbox (#ctw-tag_weight_res_textbox textarea) not cached yet. `ctwInitializeGradioElements` should handle this.");
        return false; // Initialization should occur via onUiUpdate -> ctwInitializeGradioElements
    }

    if (ctwResTextboxEl.dataset.ctwObserverAttached === 'true') {
        return true;
    }

    console.log("CTW: Found cached response textbox. Setting up MutationObserver:", ctwResTextboxEl);

    const observer = new MutationObserver((mutationsList, observerInstance) => {
        if (!ctwActiveTextarea) {
            return;
        }
        console.log("CTW: MutationObserver fired for response textbox. Active textarea:", ctwActiveTextarea.id || `(no id, placeholder: "${ctwActiveTextarea.placeholder || 'N/A'}")`);

        for(const mutation of mutationsList) {
            if (mutation.type === 'childList' || mutation.type === 'characterData' || mutation.type === 'attributes') {
                const responseJson = ctwResTextboxEl.value; // Use cached element
                // console.log("CTW: Response textbox value:", responseJson); // Reduced verbosity

                if (responseJson && responseJson.trim() !== "") {
                    try {
                        const response = JSON.parse(responseJson);
                        // console.log("CTW: Parsed response:", response); // Reduced verbosity

                        if (response.success && response.new_prompt_text !== undefined) {
                            // console.log("CTW: Success. Updating textarea with new prompt:", response.new_prompt_text); // Reduced verbosity
                            const oldScrollTop = ctwActiveTextarea.scrollTop;
                            const oldSelectionStart = ctwActiveTextarea.selectionStart;
                            const oldText = ctwActiveTextarea.value;
                            const changeInLength = response.new_prompt_text.length - oldText.length;

                            ctwActiveTextarea.value = response.new_prompt_text;

                            const newCursorPos = Math.max(0, oldSelectionStart + changeInLength);

                            ctwActiveTextarea.selectionStart = newCursorPos;
                            ctwActiveTextarea.selectionEnd = newCursorPos;
                            ctwActiveTextarea.scrollTop = oldScrollTop;
                            // console.log("CTW: Textarea updated. New cursor pos:", newCursorPos); // Reduced verbosity

                            if (window.updateInput) {
                                window.updateInput(ctwActiveTextarea);
                                // console.log("CTW: Called window.updateInput()."); // Reduced verbosity
                            } else {
                                const inputEvent = new Event('input', { bubbles: true });
                                ctwActiveTextarea.dispatchEvent(inputEvent);
                                // console.log("CTW: Dispatched input event as fallback."); // Reduced verbosity
                            }

                        } else if (response.error) {
                            console.warn("CTW Error from Python: " + response.error);
                        } else {
                            console.warn("CTW: Response not successful or new_prompt_text missing.", response);
                        }
                    } catch (e) {
                        console.error("CTW: Failed to parse response JSON.", e, "JSON was:", responseJson);
                    }

                    ctwResTextboxEl.value = ""; // Use cached element
                    const clearEvent = new Event('input', { bubbles: true });
                    ctwResTextboxEl.dispatchEvent(clearEvent); // Use cached element
                    ctwActiveTextarea = null;
                    break;
                }
            }
        }
    });

    observer.observe(ctwResTextboxEl, { childList: true, characterData: true, subtree: true, attributes: true, attributeOldValue: true }); // Use cached element
    ctwResTextboxEl.dataset.ctwObserverAttached = 'true'; // Use cached element
    console.log("CTW: Response handler (MutationObserver) successfully set up and observing for cached response textbox.");
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
                    // console.log(`CTW: Attached keydown listener to textarea in #${idFragment}`); // Reduced verbosity
                    actuallyAttachedCount++;
                }
            }
        }
    });
}

// Standard A1111 UI update hook
(
  window.onAfterUiUpdate || window.onUiUpdate || (() => {}) // Fallback to empty function if neither exists
)(() => {
  ctwInitializeGradioElements(); // Initialize/cache Gradio elements
  ctwAttachKeydownListeners(); // Attach keydown listeners

  // Setup response handler only if all necessary elements are cached and handler not already attached
  if (ctwResTextboxEl && !window.ctwTagWeightResponseHandlerAttached) {
    if (ctwSetupTagWeightResponseHandler()) {
        window.ctwTagWeightResponseHandlerAttached = true;
        console.log("CTW: Tag Weight Response Handler global flag set to true.");
    }
  }
});

console.log("Custom Tag Weighting (CTW) JavaScript loaded.");
// --- End of Custom Tag Weighting (CTW) specific JavaScript ---
