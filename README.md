# A1111 Custom Tag Weighting Extension

This extension provides an improved Ctrl+Up/Down arrow key functionality for adjusting tag weights in the prompt textareas of the Automatic1111 WebUI. It correctly handles tags with spaces and parentheses, ensuring accurate weight application.

## Features

-   Overrides the default Ctrl+Up/Down tag weighting.
-   Correctly parses and weights complex tags (e.g., `(tag with spaces:1.1)`, `(tag (with parens):1.1)`).
-   Handles repeated weighting operations on already weighted tags without incorrect nesting.
-   Always active as long as the extension is enabled.

## Installation

Place this directory in your `extensions` folder within the A1111 WebUI installation.
