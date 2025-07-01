# prompts.py

# Prompt for default explanation mode
DEFAULT_EXPLANATION_PROMPT = """以下是PDF文档中的一段上下文信息：

上下文：
{context_text}

在这段上下文中，你高亮了以下文本：

高亮文本：
{selected_text}

请结合上下文，深入浅出地解释这段高亮文字的含义、背景和重要性。"""

# Prompt for custom question mode
CUSTOM_QUESTION_PROMPT = """以下是PDF文档中的一段上下文信息：

上下文：
{context_text}

在这段上下文中，你高亮了以下文本：

高亮文本：
{selected_text}

我的问题是：{user_question}"""
