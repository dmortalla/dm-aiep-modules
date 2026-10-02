"""Streamlit demonstration UI for Module 1."""

import asyncio
from pathlib import Path

import streamlit as st
from ai_engineering_foundations.credentials import (
    CredentialSecurityError,
    delete_local_env,
    read_local_credential,
    read_local_credential_names,
    read_os_credential,
    remove_local_credentials,
    save_local_credentials,
)
from ai_engineering_foundations.models import LLMRequest
from ai_engineering_foundations.providers.anthropic_provider import AnthropicProvider
from ai_engineering_foundations.providers.gemini_provider import GeminiProvider
from ai_engineering_foundations.providers.openai_provider import OpenAIProvider
from ai_engineering_foundations.service import LLMService, LLMServiceError

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

PROVIDER_CONFIG = {
    "OpenAI": {
        "service_name": "openai",
        "environment_key": "OPENAI_API_KEY",
        "default_model": "gpt-5.6-terra",
    },
    "Anthropic": {
        "service_name": "anthropic",
        "environment_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-5-5",
    },
    "Gemini": {
        "service_name": "gemini",
        "environment_key": "GEMINI_API_KEY",
        "default_model": "gemini-3.8-flash",
    },
}


def authorized_session_key(provider_label: str) -> str | None:
    """Return only a credential explicitly authorized for this UI session."""
    service_name = PROVIDER_CONFIG[provider_label]["service_name"]
    value = st.session_state.get(f"authorized_{service_name}")

    if isinstance(value, str) and value:
        return value

    return None


def build_provider(provider_label: str):
    """Build a provider only from an explicitly authorized session credential."""
    api_key = authorized_session_key(provider_label)

    if not api_key:
        raise ValueError(
            f"{provider_label} has no API credential authorized for this session. "
            "Use Manage API Keys to authorize one explicitly."
        )

    if provider_label == "OpenAI":
        return OpenAIProvider(api_key=api_key)

    if provider_label == "Anthropic":
        return AnthropicProvider(api_key=api_key)

    return GeminiProvider(api_key=api_key)


async def generate_response(
    provider_label: str,
    request: LLMRequest,
):
    """Run one provider-independent generation request."""
    provider = build_provider(provider_label)
    service_name = PROVIDER_CONFIG[provider_label]["service_name"]

    service = LLMService({service_name: provider})
    return await service.generate(service_name, request)


async def stream_response(
    provider_label: str,
    request: LLMRequest,
):
    """Yield provider chunks directly to the Streamlit rendering boundary."""
    provider = build_provider(provider_label)
    service_name = PROVIDER_CONFIG[provider_label]["service_name"]
    service = LLMService({service_name: provider})

    async for chunk in service.stream(service_name, request):
        yield chunk


def clear_interaction() -> None:
    """Clear user-visible prompt and generated-result state."""
    st.session_state["prompt"] = ""
    st.session_state.pop("response", None)
    st.session_state.pop("streamed_response", None)


def clear_authorized_credentials() -> None:
    """Return this Streamlit session to the zero-key state."""
    for config in PROVIDER_CONFIG.values():
        service_name = config["service_name"]
        st.session_state.pop(f"authorized_{service_name}", None)
        st.session_state[f"credential_{service_name}"] = ""

    st.session_state["credential_notice"] = (
        "Session credentials cleared. This session is back in the zero-key state."
    )
    st.session_state["credential_notice_type"] = "success"


def authorize_entered_keys() -> None:
    """Authorize entered credentials for this session without writing to disk."""
    authorized = 0

    for config in PROVIDER_CONFIG.values():
        service_name = config["service_name"]
        widget_key = f"credential_{service_name}"
        value = st.session_state.get(widget_key, "").strip()

        if value:
            if "\n" in value or "\r" in value:
                st.session_state["credential_notice"] = (
                    "Credential authorization was rejected by the security boundary."
                )
                st.session_state["credential_notice_type"] = "error"
                return

            st.session_state[f"authorized_{service_name}"] = value
            st.session_state[widget_key] = ""
            authorized += 1

    if not authorized:
        st.session_state["credential_notice"] = (
            "Enter at least one API key before authorizing session credentials."
        )
        st.session_state["credential_notice_type"] = "warning"
        return

    st.session_state["credential_notice"] = (
        "Entered credentials authorized for this session only."
    )
    st.session_state["credential_notice_type"] = "success"


def save_entered_keys() -> None:
    """Persist entered credentials only after explicit user action."""
    updates = {}

    for config in PROVIDER_CONFIG.values():
        widget_key = f"credential_{config['service_name']}"
        value = st.session_state.get(widget_key, "").strip()

        if value:
            updates[config["environment_key"]] = value

    if not updates:
        st.session_state["credential_notice"] = (
            "Enter at least one API key before saving locally."
        )
        st.session_state["credential_notice_type"] = "warning"
        return

    try:
        save_local_credentials(ENV_PATH, updates)
    except CredentialSecurityError:
        st.session_state["credential_notice"] = (
            "The credential update was rejected by the security boundary."
        )
        st.session_state["credential_notice_type"] = "error"
        return

    for config in PROVIDER_CONFIG.values():
        st.session_state[f"credential_{config['service_name']}"] = ""

    st.session_state["credential_notice"] = (
        "Selected credentials saved locally. They are not automatically "
        "authorized for this session."
    )
    st.session_state["credential_notice_type"] = "success"


def authorize_local_key(provider_label: str) -> None:
    """Explicitly authorize one stored local credential for this session."""
    config = PROVIDER_CONFIG[provider_label]
    value = read_local_credential(ENV_PATH, config["environment_key"])

    if not value:
        st.session_state["credential_notice"] = (
            f"No project-local {provider_label} credential is stored."
        )
        st.session_state["credential_notice_type"] = "warning"
        return

    st.session_state[f"authorized_{config['service_name']}"] = value
    st.session_state["credential_notice"] = (
        f"{provider_label} local credential authorized for this session."
    )
    st.session_state["credential_notice_type"] = "success"


def authorize_os_key(provider_label: str) -> None:
    """Explicitly authorize one OS credential for this session."""
    config = PROVIDER_CONFIG[provider_label]
    value = read_os_credential(config["environment_key"])

    if not value:
        st.session_state["credential_notice"] = (
            f"No {provider_label} credential exists in the OS environment."
        )
        st.session_state["credential_notice_type"] = "warning"
        return

    st.session_state[f"authorized_{config['service_name']}"] = value
    st.session_state["credential_notice"] = (
        f"{provider_label} OS credential authorized for this session."
    )
    st.session_state["credential_notice_type"] = "success"


def remove_keys() -> None:
    """Remove only explicitly selected project-local credentials."""
    names = {
        config["environment_key"]
        for config in PROVIDER_CONFIG.values()
        if st.session_state.get(f"remove_{config['service_name']}", False)
    }

    if not names:
        st.session_state["credential_notice"] = (
            "Select at least one local credential to remove."
        )
        st.session_state["credential_notice_type"] = "warning"
        return

    try:
        remove_local_credentials(ENV_PATH, names)
    except CredentialSecurityError:
        st.session_state["credential_notice"] = (
            "The credential removal was rejected by the security boundary."
        )
        st.session_state["credential_notice_type"] = "error"
        return

    st.session_state["credential_notice"] = (
        "Selected project-local credentials removed. Existing session and "
        "operating-system credentials were not changed."
    )
    st.session_state["credential_notice_type"] = "success"


def delete_env() -> None:
    """Delete only the project-local credential file after confirmation."""
    if not st.session_state.get("confirm_delete_env", False):
        st.session_state["credential_notice"] = (
            "Confirm local .env deletion before continuing."
        )
        st.session_state["credential_notice_type"] = "warning"
        return

    delete_local_env(ENV_PATH)
    st.session_state["confirm_delete_env"] = False
    st.session_state["credential_notice"] = (
        "Project-local .env deleted. Existing session and operating-system "
        "credentials were not changed."
    )
    st.session_state["credential_notice_type"] = "success"


st.set_page_config(
    page_title="LLM SDK Foundations",
    layout="wide",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("LLM SDK Foundations")
st.caption(
    "Provider-independent async interaction with OpenAI, Anthropic, and Gemini."
)

with st.sidebar:
    st.header("Configuration")

    provider_label = st.selectbox(
        "Provider",
        options=list(PROVIDER_CONFIG),
    )

    selected_config = PROVIDER_CONFIG[provider_label]

    model = st.text_input(
        "Model",
        value=selected_config["default_model"],
    )

    reasoning_effort = None
    thinking_level = None

    if provider_label == "OpenAI":
        reasoning_effort = st.selectbox(
            "Reasoning effort",
            options=["none", "low", "medium", "high"],
            index=1,
        )
    elif provider_label == "Anthropic":
        adaptive_thinking = st.toggle(
            "Adaptive thinking",
            value=True,
        )

        if adaptive_thinking:
            reasoning_effort = "medium"
    else:
        thinking_level = st.selectbox(
            "Thinking level",
            options=["low", "medium", "high"],
            index=1,
        )

    max_tokens = st.number_input(
        "Maximum output tokens",
        min_value=1,
        max_value=8192,
        value=512,
        step=1,
    )

    stream_enabled = st.toggle(
        "Stream response",
        value=False,
    )

    if authorized_session_key(provider_label):
        st.success(f"{provider_label}: session credential authorized.")
    else:
        st.info(f"{provider_label}: zero-key state.")

    st.divider()

    with st.expander("Manage API Keys"):
        st.info(
            "Zero-key startup: no API credential is automatically authorized. "
            "Session-only authorization is the recommended default."
        )

        st.caption(
            "Enter credentials below. Existing secret values are never displayed."
        )

        for provider_name, config in PROVIDER_CONFIG.items():
            st.text_input(
                f"{provider_name} API key",
                type="password",
                key=f"credential_{config['service_name']}",
                placeholder="Enter key",
            )

        st.button(
            "Authorize entered keys for this session",
            on_click=authorize_entered_keys,
            use_container_width=True,
            type="primary",
        )

        st.button(
            "Clear all session credentials",
            on_click=clear_authorized_credentials,
            use_container_width=True,
        )

        st.divider()
        st.caption("Optional project-local persistence")

        st.button(
            "Save entered keys locally",
            on_click=save_entered_keys,
            use_container_width=True,
        )

        local_names = read_local_credential_names(ENV_PATH)

        for provider_name, config in PROVIDER_CONFIG.items():
            environment_name = config["environment_key"]
            is_local = environment_name in local_names

            if is_local:
                st.button(
                    f"Authorize stored {provider_name} key",
                    key=f"authorize_local_{config['service_name']}",
                    on_click=authorize_local_key,
                    args=(provider_name,),
                    use_container_width=True,
                )

            st.checkbox(
                f"Remove stored {provider_name} key",
                key=f"remove_{config['service_name']}",
                disabled=not is_local,
                help=(
                    "Select this project-local credential for removal."
                    if is_local
                    else "No project-local credential is stored for this provider."
                ),
            )

        st.button(
            "Remove selected stored keys",
            on_click=remove_keys,
            use_container_width=True,
        )

        st.checkbox(
            "I understand this deletes the project-local .env file",
            key="confirm_delete_env",
        )

        st.button(
            "Delete local .env",
            on_click=delete_env,
            use_container_width=True,
        )

        st.divider()
        st.caption("Optional operating-system credentials")

        for provider_name, config in PROVIDER_CONFIG.items():
            environment_name = config["environment_key"]

            if read_os_credential(environment_name):
                st.button(
                    f"Authorize OS {provider_name} key",
                    key=f"authorize_os_{config['service_name']}",
                    on_click=authorize_os_key,
                    args=(provider_name,),
                    use_container_width=True,
                )
            else:
                st.caption(f"{provider_name}: no OS credential detected.")

        notice = st.session_state.get("credential_notice")
        notice_type = st.session_state.get("credential_notice_type")

        if notice:
            if notice_type == "success":
                st.success(notice)
            elif notice_type == "error":
                st.error(notice)
            else:
                st.warning(notice)

    st.divider()
    st.subheader("API Key Safety")

    stored_local_credentials = read_local_credential_names(ENV_PATH)

    st.info(
        "This app starts in a zero-key state. No API key is automatically "
        "authorized when the app starts. Explicitly authorize a credential "
        "before making a provider request."
    )

    if stored_local_credentials:
        st.warning(
            "Project-local API credentials are currently stored. Before leaving "
            "this application, remove local keys you no longer need."
        )
    else:
        st.success("No project-local API keys are currently stored.")

    st.caption(
        "Session-only credentials are recommended. Removing a key from this app "
        "does not revoke it with the provider. For cost protection, configure "
        "provider-side spending limits, budgets, or usage alerts where available. "
        "Revoke compromised or retired keys directly with the API provider."
    )

st.subheader("Prompt")

prompt = st.text_area(
    "Enter a prompt",
    height=180,
    placeholder="Ask the selected model something...",
    label_visibility="collapsed",
    key="prompt",
)

generate_column, clear_column = st.columns([4, 1])

with generate_column:
    submit = st.button(
        "Generate response",
        type="primary",
        use_container_width=True,
    )

with clear_column:
    st.button(
        "Clear",
        on_click=clear_interaction,
        use_container_width=True,
    )

if submit:
    if not prompt.strip():
        st.warning("Enter a prompt before generating a response.")
    elif not model.strip():
        st.warning("Enter a model name before generating a response.")
    elif not authorized_session_key(provider_label):
        st.warning(
            f"{provider_label} has no credential authorized for this session. "
            "Open Manage API Keys to authorize one."
        )
    else:
        request = LLMRequest(
            prompt=prompt,
            model=model,
            max_tokens=int(max_tokens),
            reasoning_effort=reasoning_effort,
            thinking_level=thinking_level,
        )

        try:
            if stream_enabled:
                st.subheader("Streaming Response")

                with st.spinner(f"Connecting to {provider_label}..."):
                    rendered_text = st.write_stream(
                        stream_response(
                            provider_label,
                            request,
                        )
                    )

                if not rendered_text:
                    st.info("The provider returned no text.")
            else:
                with st.spinner(f"Generating with {provider_label}..."):
                    response = asyncio.run(
                        generate_response(
                            provider_label,
                            request,
                        )
                    )

                st.subheader("Response")
                st.markdown(response.content or "_No text returned._")

                st.subheader("Normalized Metadata")

                (
                    metric_provider,
                    metric_input,
                    metric_output,
                    metric_total,
                ) = st.columns(4)

                metric_provider.metric(
                    "Provider",
                    response.provider,
                )
                metric_input.metric(
                    "Input tokens",
                    response.usage.input_tokens,
                )
                metric_output.metric(
                    "Output tokens",
                    response.usage.output_tokens,
                )
                metric_total.metric(
                    "Total tokens",
                    response.usage.total_tokens,
                )

                st.caption(f"Model: {response.model}")

        except (ValueError, LLMServiceError) as exc:
            st.error(str(exc))
        except Exception:
            st.error(
                "The provider request failed unexpectedly. "
                "Check the authorized credential, model name, and network connection."
            )

st.divider()

st.caption(
    "Security model: zero-key startup, explicit credential authorization, "
    "session-only credentials by default, and optional explicit persistence."
)
