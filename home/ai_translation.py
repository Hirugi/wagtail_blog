import anthropic as anthropic
from anthropic.types import MessageParam
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)


class TranslationError(Exception):
    pass


def translate_text(content: str, system_prompt: str, provider: str, api_key: str, model: str, base_url: str = '') -> str:
    """Translate content using the configured AI provider."""
    if not content or not content.strip():
        return content
    if provider == 'anthropic':
        return _translate_anthropic(content, system_prompt, api_key, model)
    else:
        return _translate_openai_compat(content, system_prompt, api_key, model, base_url)


def _translate_anthropic(content: str, system_prompt: str, api_key: str, model: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    messages: list[MessageParam] = [
        MessageParam(role="user", content=content),
    ]
    message = client.messages.create(
        model=model or 'claude-sonnet-4-6',
        max_tokens=8096,
        system=system_prompt,
        messages=messages,
    )
    return message.content[0].text


def _translate_openai_compat(content: str, system_prompt: str, api_key: str, model: str, base_url: str = '') -> str:
    kwargs = {'api_key': api_key}
    if base_url:
        kwargs['base_url'] = base_url
    client = OpenAI(**kwargs)
    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(role="user", content=content),
    ]
    response = client.chat.completions.create(
        model=model or 'gpt-4o',
        messages=messages,
    )
    return response.choices[0].message.content
