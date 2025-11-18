import os
from typing import Any

import yaml
from jinja2 import Template


class PromptManager:
    """Manages loading and formatting of prompts from a directory."""

    def __init__(self, template_dir: str = "prompt_templates"):
        """
        Initializes the PromptManager.

        Args:
            template_dir: The directory where prompt YAML files are stored.
        """
        self.template_dir = template_dir
        self.prompts: dict[str, dict[str, Any]] = {}
        self._load_prompts()

    def _load_prompts(self):
        """Loads all prompt YAML files from the template directory."""
        if not os.path.isdir(self.template_dir):
            raise FileNotFoundError(
                f"Prompt template directory not found: {self.template_dir}"
            )

        for filename in os.listdir(self.template_dir):
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                filepath = os.path.join(self.template_dir, filename)
                with open(filepath, encoding="utf-8") as f:
                    try:
                        prompt_data = yaml.safe_load(f)
                        if isinstance(prompt_data, list):
                            for prompt in prompt_data:
                                if "id" in prompt:
                                    self.prompts[prompt["id"]] = prompt
                    except yaml.YAMLError as e:
                        print(f"Error loading prompt file {filename}: {e}")

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None:
        """Gets the raw prompt data for a given ID."""
        return self.prompts.get(prompt_id)

    def get_formatted_prompt(self, prompt_id: str, **kwargs) -> str | None:
        """
        Gets a formatted prompt string for a given ID and context variables.

        Args:
            prompt_id: The ID of the prompt to format.
            **kwargs: The variables to substitute into the prompt template.

        Returns:
            The formatted prompt string, or None if the prompt ID is not found.
        """
        prompt_data = self.get_prompt(prompt_id)
        if not prompt_data:
            return None

        template_str = prompt_data.get("template", "")
        template = Template(template_str)

        return template.render(**kwargs)
