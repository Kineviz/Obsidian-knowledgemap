#!/usr/bin/env python3
"""
Prompt Loader for Obsidian Knowledge Map
Loads AI prompts from configuration files and provides them to the extraction modules.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class PromptConfig:
    """Configuration for a single prompt"""
    role: str
    content: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    response_format: Optional[str] = None


class PromptLoader:
    """Loads and manages AI prompts from configuration files"""
    
    def __init__(self, prompts_file: Optional[Path] = None):
        """
        Initialize the prompt loader
        
        Args:
            prompts_file: Path to the prompts configuration file. 
                         Defaults to prompts.yaml in the project root.
        """
        if prompts_file is None:
            # Default to prompts.yaml in the project root
            project_root = Path(__file__).parent.parent
            prompts_file = project_root / "prompts.yaml"
        
        self.prompts_file = prompts_file
        self._prompts_data = None
        self._load_prompts()
    
    def _load_prompts(self):
        """Load prompts from the configuration file"""
        try:
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                self._prompts_data = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompts configuration file not found: {self.prompts_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in prompts configuration file: {e}")
    
    def get_system_prompt(self, prompt_name: str) -> PromptConfig:
        """
        Get a system prompt by name
        
        Args:
            prompt_name: Name of the prompt (e.g., 'relationship_extraction')
            
        Returns:
            PromptConfig object with the prompt details
        """
        if not self._prompts_data:
            raise RuntimeError("Prompts not loaded")
        
        system_prompts = self._prompts_data.get('system_prompts', {})
        if prompt_name not in system_prompts:
            raise KeyError(f"System prompt '{prompt_name}' not found in configuration")
        
        prompt_data = system_prompts[prompt_name]
        model_config = self._prompts_data.get('model_config', {})
        
        return PromptConfig(
            role=prompt_data['role'],
            content=prompt_data['content'],
            model=model_config.get('relationship_extraction_model'),
            temperature=model_config.get('relationship_extraction_temperature'),
            response_format=model_config.get('relationship_extraction_response_format')
        )
    
    def get_user_prompt(self, prompt_name: str, **kwargs) -> PromptConfig:
        """
        Get a user prompt by name with variable substitution
        
        Args:
            prompt_name: Name of the prompt (e.g., 'relationship_extraction')
            **kwargs: Variables to substitute in the prompt content
            
        Returns:
            PromptConfig object with the prompt details
        """
        if not self._prompts_data:
            raise RuntimeError("Prompts not loaded")
        
        user_prompts = self._prompts_data.get('user_prompts', {})
        if prompt_name not in user_prompts:
            raise KeyError(f"User prompt '{prompt_name}' not found in configuration")
        
        prompt_data = user_prompts[prompt_name]
        
        # Substitute variables in the content
        content = prompt_data['content'].format(**kwargs)
        
        return PromptConfig(
            role=prompt_data['role'],
            content=content
        )
    
    def get_prompt_pair(self, prompt_name: str, **kwargs) -> List[Dict[str, str]]:
        """
        Get both system and user prompts as a message pair for OpenAI API
        
        Args:
            prompt_name: Base name of the prompt (e.g., 'relationship_extraction')
            **kwargs: Variables to substitute in the user prompt
            
        Returns:
            List of message dictionaries ready for OpenAI API
        """
        system_prompt = self.get_system_prompt(prompt_name)
        user_prompt = self.get_user_prompt(prompt_name, **kwargs)
        
        return [
            {
                "role": system_prompt.role,
                "content": system_prompt.content
            },
            {
                "role": user_prompt.role,
                "content": user_prompt.content
            }
        ]
    
    def get_model_config(self, prompt_name: str) -> Dict[str, Any]:
        """
        Get model configuration for a specific prompt
        
        Args:
            prompt_name: Name of the prompt
            
        Returns:
            Dictionary with model configuration
        """
        if not self._prompts_data:
            raise RuntimeError("Prompts not loaded")
        
        model_config = self._prompts_data.get('model_config', {})
        prompt_selection = self._prompts_data.get('prompt_selection', {})
        
        # Get the actual prompt name to use
        actual_prompt_name = prompt_selection.get(prompt_name, prompt_name)
        
        return {
            "model": model_config.get('relationship_extraction_model', 'gpt-4o-mini'),
            "temperature": model_config.get('relationship_extraction_temperature', 0.1),
            "response_format": model_config.get('relationship_extraction_response_format', 'json_object')
        }
    
    def list_available_prompts(self) -> Dict[str, List[str]]:
        """
        List all available prompts
        
        Returns:
            Dictionary with 'system' and 'user' keys containing lists of prompt names
        """
        if not self._prompts_data:
            raise RuntimeError("Prompts not loaded")
        
        return {
            'system': list(self._prompts_data.get('system_prompts', {}).keys()),
            'user': list(self._prompts_data.get('user_prompts', {}).keys())
        }


# Global prompt loader instance
_prompt_loader = None

def get_prompt_loader() -> PromptLoader:
    """Get the global prompt loader instance"""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


def reload_prompts():
    """Reload prompts from the configuration file"""
    global _prompt_loader
    _prompt_loader = PromptLoader()
    return _prompt_loader
