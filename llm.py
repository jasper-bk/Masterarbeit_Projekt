#!/usr/bin/env python3

import os
from abc import ABC, abstractmethod
from typing import Dict, Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_community.llms import Ollama, OpenAI
import requests
from retry import retry
import argparse
import json
import dotenv

class AIAssistant():
    """AI base assistant with multi-provider support"""

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "deepseek-r1",
        langchain: bool = False,
        api_key: Optional[str] = None
    ):
        self.provider = provider
        self.model = model
        self.langchain = langchain
        self.api_key = api_key or os.getenv("AI_API_KEY")

        self._init_model()

    def _init_model(self):
        """Initialize the language model based on configuration"""
        if self.langchain:
            self.llm = self._init_langchain_model()
        else:
            self.base_url = self._get_base_url()

    def _init_langchain_model(self) -> BaseLanguageModel:
        """Initialize LangChain model instance"""
        if self.provider == "ollama":
            return Ollama(
                model=self.model,
                base_url="http://localhost:11434"
            )
        elif self.provider == "openai":
            return OpenAI(
                model=self.model,
                openai_api_key=self.api_key
            )
        # To-Do: Add Nexus or call it custom
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    @retry(tries=3, delay=2, backoff=2)
    def generate_response(self, prompt: str) -> str:
        """Generate response with retry logic"""
        try:
            if self.langchain:
                return self.llm.invoke(prompt)
            else:
                return self._direct_api_call(prompt)
        except Exception as e:
            self._handle_error(e)
            return "Error generating recommendation"

    def _handle_error(self, error: Exception):
        """Handle and log errors"""
        print(f"AI Service Error: {str(error)}")
        # Add logging service integration here

    #####################################
    # Methods for use without langchain #
    #####################################

    def _get_base_url(self) -> str:
        """Get base URL for API endpoint"""
        urls = {
            "ollama": "http://127.0.0.1:11434",
            "openai": "https://api.openai.com/v1",
            "nexus" : "https://genai-nexus.api.corpinter.net"
        }
        return urls.get(self.provider)

    def _direct_api_call(self, prompt: str) -> str:
        """Direct API call without LangChain middleware"""
        endpoint = {
            "ollama": "/api/generate",
            "openai": "/chat/completions",
            "nexus" : "/apikey/openai/deployments/gpt-4o/chat/completions?api-version=2024-06-01"
        }[self.provider]

        headers = {"Content-Type": "application/json"}

        if self.provider == "openai":
            headers["Authorization"] = f"Bearer {self.api_key}"

        if self.provider == "nexus":
            headers["api-key"] = self.api_key

        payload = self._build_payload(prompt)

        response = requests.post(
            f"{self.base_url}{endpoint}",
            headers=headers,
            json=payload
        )
        return self._parse_response(response)

    def _build_payload(self, prompt: str) -> Dict:
        """Build provider-specific API payload"""
        if self.provider == "ollama":
            return {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
        elif self.provider in ["openai", "nexus"]:
            return {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}]
            }

    def _parse_response(self, response: requests.Response) -> str:
        """Parse API response based on provider"""
        if response.status_code != 200:
            raise ConnectionError(f"API Error: {response.text}")

        if self.provider == "ollama":
            return response.json().get("response", "")
        elif self.provider in ["openai", "nexus"]:
            return response.json()["choices"][0]["message"]["content"]

def main():
    """Command line interface for manual testing"""
    parser = argparse.ArgumentParser(
        description="AI Assistant"
    )
    parser.add_argument("--provider", default="ollama",
                      help="AI service provider (ollama|openai)")
    parser.add_argument("--model", default="deepseek-r1:14b",
                      help="Model name/version")
    parser.add_argument("--langchain", action="store_true",
                      help="Use LangChain integration")
    parser.add_argument("--prompt", required=True,
                      help="Input prompt for analysis")

    args = parser.parse_args()

    assistant = AIAssistant(
        provider=args.provider,
        model=args.model,
        langchain=args.langchain
    )

    result = assistant.generate_response(args.prompt)
    print(json.dumps(result, indent=2))

def manual_ollama_test():
    assistant = AIAssistant(
        provider="ollama",
        model="deepseek-r1:14b"
    )

    result = assistant.generate_response("Count to 3")
    print(result)

def manual_nexus_test():
    dotenv.load_dotenv()
    assistant = AIAssistant(
        provider="nexus"
    )

    result = assistant.generate_response("Count to 3")
    print(result)

if __name__ == "__main__":
    manual_nexus_test()
    #main()
