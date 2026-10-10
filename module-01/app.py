"""Streamlit demonstration UI for Module 1."""

import asyncio

import streamlit as st
from ai_engineering_foundations.models import LLMRequest
from ai_engineering_foundations.providers.anthropic_provider import AnthropicProvider
from ai_engineering_foundations.providers.gemini_provider import GeminiProvider
from ai_engineering_foundations.providers.openai_provider import OpenAIProvider
from ai_engineering_foundations.service import LLMService, LLMServiceError

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
            "Public deployment: API keys are session-only and are not saved "
            "to a project-local credential file."
        )

        st.caption(
            "Enter only credentials you want to authorize for this browser session."
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

        notice = st.session_state.get("credential_notice")
        notice_type = st.session_state.get("credential_notice_type")

        if notice:
            if notice_type == "success":
                st.success(notice)
            elif notice_type == "warning":
                st.warning(notice)
            else:
                st.error(notice)

    st.markdown(
        """
        <style>
        @keyframes securityPulse {
            0%, 100% { opacity: 0.72; }
            50% { opacity: 1; }
        }

        .session-security-reminder {
            animation: securityPulse 3s ease-in-out infinite;
            border: 1px solid rgba(250, 166, 26, 0.45);
            border-radius: 0.5rem;
            padding: 0.65rem 0.75rem;
            margin: 0.75rem 0;
            font-size: 0.86rem;
        }

        @media (prefers-reduced-motion: reduce) {
            .session-security-reminder {
                animation: none;
            }
        }
        </style>

        <div class="session-security-reminder">
        <strong>Security reminder:</strong>
        When finished, click <strong>Clear session credentials</strong> and
        close this tab, especially on a shared computer.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("API Key Safety")

    st.info(
        "This public app starts in a zero-key state. API keys must be explicitly "
        "authorized for the current session and are not persisted by this UI."
    )

    st.caption(
        "Clearing a session credential does not revoke the API key with its provider. "
        "Revoke compromised or retired keys directly with the provider and use "
        "provider-side spending limits or usage alerts where available."
    )
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
    "session-only credentials with no public UI persistence."
)

st.caption(
    "Developed from Techademy AI Engineering program requirements. "
    "Independent implementation, engineering enhancements, and deployment."
)
