"""
CSS Style Templates

This module contains all CSS templates for UI components, organized by component type.
Templates use variable substitution to enable dynamic styling based on configuration.
"""

# Chat Panel Component Template
CHAT_PANEL_TEMPLATE = """
QWidget#chat_panel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 $gradient_start, stop:1 $gradient_end);
    border-radius: ${border_radius}px;
    padding: ${padding}px;
    margin: ${margin}px;
}

QWidget#chat_header {
    background: transparent;
    color: $header_text_color;
    font-size: ${header_font_size}px;
    font-weight: bold;
    padding: ${header_padding}px;
    border-radius: ${header_border_radius}px;
}

QLabel#chat_title {
    color: $header_text_color;
    font-size: ${header_font_size}px;
    font-weight: bold;
    background: transparent;
}

QPushButton#clear_button {
    background-color: $button_bg_color;
    color: $button_text_color;
    border: none;
    border-radius: ${button_border_radius}px;
    padding: ${button_padding}px;
    font-size: ${button_font_size}px;
}

QPushButton#clear_button:hover {
    background-color: $button_hover_bg_color;
}

QPushButton#suggestion_button {
    background-color: $suggestion_bg_color;
    color: $suggestion_text_color;
    border: ${suggestion_border_width}px solid $suggestion_border_color;
    border-radius: ${suggestion_border_radius}px;
    padding: ${suggestion_padding}px;
    margin: ${suggestion_margin}px;
    font-size: ${suggestion_font_size}px;
}

QPushButton#suggestion_button:hover {
    background-color: $suggestion_hover_bg_color;
    border-color: $suggestion_hover_border_color;
}

QWidget#empty_state {
    background: transparent;
    color: $empty_text_color;
    padding: ${empty_padding}px;
}

QLabel#empty_icon {
    font-size: ${empty_icon_size}px;
    color: $empty_icon_color;
    background: $empty_icon_bg;
    border-radius: ${empty_icon_radius}px;
    padding: ${empty_icon_padding}px;
}

QLabel#empty_title {
    font-size: ${empty_title_size}px;
    font-weight: bold;
    color: $empty_title_color;
}

QLabel#empty_description {
    font-size: ${empty_desc_size}px;
    color: $empty_desc_color;
    line-height: 1.4;
}
"""

# Chat Input Component Template
CHAT_INPUT_TEMPLATE = """
QTextEdit#text_input {
    background-color: $input_bg_color;
    border: ${input_border_width}px solid $input_border_color;
    border-radius: ${input_border_radius}px;
    padding: ${input_padding}px;
    font-size: ${input_font_size}px;
    color: $input_text_color;
    font-family: $input_font_family;
}

QTextEdit#text_input:focus {
    border: ${input_focus_border_width}px solid $input_focus_border_color;
    background-color: $input_focus_bg_color;
    padding: ${input_focus_padding}px;
}

QPushButton#send_button {
    background-color: $button_bg_color;
    color: $button_text_color;
    border: none;
    border-radius: ${button_border_radius}px;
    padding: ${button_padding}px;
    font-weight: bold;
    font-size: ${button_font_size}px;
    min-width: ${button_min_width}px;
}

QPushButton#send_button:hover {
    background-color: $button_hover_bg_color;
}

QPushButton#send_button:pressed {
    background-color: $button_pressed_bg_color;
}

QPushButton#send_button:disabled {
    background-color: $button_disabled_bg_color;
    color: $button_disabled_text_color;
}

QWidget#input_container {
    background: transparent;
    padding: ${container_padding}px;
    margin: ${container_margin}px;
}
"""

# Chat Message Component Template
CHAT_MESSAGE_TEMPLATE = """
QWidget#message_container {
    background: transparent;
    padding: ${message_padding}px;
    margin: ${message_margin}px;
}

QWidget#user_message {
    background-color: $user_bg_color;
    color: $user_text_color;
    border: ${user_border_width}px solid $user_border_color;
    border-radius: ${user_border_radius}px;
    padding: ${user_padding}px;
    margin: ${user_margin}px;
}

QWidget#ai_message {
    background-color: $ai_bg_color;
    color: $ai_text_color;
    border: ${ai_border_width}px solid $ai_border_color;
    border-radius: ${ai_border_radius}px;
    padding: ${ai_padding}px;
    margin: ${ai_margin}px;
}

QLabel#message_text {
    font-size: ${message_font_size}px;
    line-height: 1.4;
    background: transparent;
    color: inherit;
}

QLabel#message_timestamp {
    font-size: ${timestamp_font_size}px;
    color: $timestamp_color;
    background: transparent;
}
"""

# Loading Indicator Component Template  
LOADING_INDICATOR_TEMPLATE = """
QWidget#loading_container {
    background-color: $loading_bg_color;
    border: ${loading_border_width}px solid $loading_border_color;
    border-radius: ${loading_border_radius}px;
    padding: ${loading_padding}px;
}

QLabel#loading_text {
    color: $loading_text_color;
    font-size: ${loading_font_size}px;
    background: transparent;
}

QWidget#loading_spinner {
    background: transparent;
    min-width: ${spinner_size}px;
    min-height: ${spinner_size}px;
}
"""

# Template registry - maps component names to templates
STYLE_TEMPLATES = {
    'chat_panel': CHAT_PANEL_TEMPLATE,
    'chat_input': CHAT_INPUT_TEMPLATE,
    'chat_message': CHAT_MESSAGE_TEMPLATE,
    'loading_indicator': LOADING_INDICATOR_TEMPLATE
} 