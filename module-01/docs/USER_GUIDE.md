# Module 1 User Guide

## Python, APIs, and LLM SDK Foundations

This guide is the fastest path from opening Module 1 to successfully using and understanding its Streamlit application.

Module 1 demonstrates one provider-independent interface over OpenAI, Anthropic, and Gemini, including asynchronous execution, streaming, normalized responses, token usage, bounded provider configuration, and session-only credential authorization.

A first review should take about 5–10 minutes.

---

## 1. What You Need

- Python 3.12
- `uv` installed
- This repository cloned locally
- An API key for OpenAI, Anthropic, or Gemini only if you want to make a real provider request

You do not need an API key merely to launch and inspect the application. It starts in a zero-key state.

This guide assumes a local launch from the repository. It does not claim a hosted Module 1 deployment.

---

## 2. Launch the Application

From the repository root:

```powershell
uv sync
uv run streamlit run module-01/app.py
```

Streamlit should open the **LLM SDK Foundations** application in your browser.

In the sidebar you should see:

- **Provider**
- **Model**
- a provider-specific reasoning control
- **Maximum output tokens**
- **Stream response**
- **Manage API Keys**
- **API Key Safety**

The main area contains the prompt field plus **Generate response** and **Clear**.

---

## 3. First Check — Confirm the Safe Zero-Key State

Before entering any credential:

1. Choose a provider in **Provider**.
2. Confirm the sidebar reports `<Provider>: zero-key state.`
3. Enter this prompt:

   `Explain asynchronous API calls in two sentences.`

4. Press **Generate response**.

### Expected result

The application should refuse to make the provider request and report that the selected provider has no credential authorized for the current session.

### What this proves

Selecting a provider does not grant execution authority. A provider credential must be explicitly authorized for the current Streamlit session.

---

## 4. Authorize a Provider Credential

Only do this if you want to exercise a real provider request.

1. Expand **Manage API Keys**.
2. Enter a key in one of these fields:
   - **OpenAI API key**
   - **Anthropic API key**
   - **Gemini API key**
3. Press **Authorize entered keys for this session**.
4. Confirm the success notice.
5. Select the matching provider.
6. Confirm the sidebar reports `<Provider>: session credential authorized.`

The credential input is cleared after authorization and the authorized value remains only in Streamlit session state.

### Security note

Use only a credential you intend to authorize for this session. When finished, press **Clear all session credentials** and close the browser tab.

Clearing the Streamlit session credential does not revoke the API key with its provider. Revoke a compromised or retired key directly through that provider.

---

## 5. Run a Standard Non-Streaming Request

1. Select the authorized **Provider**.
2. Review the prefilled **Model** value.
3. If necessary, replace it with a model available to your provider account.
4. Leave **Stream response** disabled.
5. Leave **Maximum output tokens** at `512` for the first test.
6. Enter:

   `Explain why provider-independent interfaces are useful in AI engineering.`

7. Press **Generate response**.

### Expected result

A successful request should display:

- **Response**
- **Normalized Metadata**
- provider name
- input-token count
- output-token count
- total-token count
- model name

### What this proves

Provider-specific SDK behavior is normalized behind the Module 1 service boundary so the application consumes one consistent response and token-usage model.

---

## 6. Run a Streaming Request

1. Keep a valid provider credential authorized.
2. Enable **Stream response**.
3. Enter:

   `Give me five concise benefits of asynchronous Python.`

4. Press **Generate response**.

### Expected result

The application should display **Streaming Response** and render provider chunks incrementally.

If the provider returns no text, the application reports that condition instead of presenting an empty result as success.

### What this proves

Streaming uses the same provider-independent service boundary while response chunks are passed incrementally to the Streamlit presentation layer.

---

## 7. Explore Provider-Specific Reasoning Controls

The sidebar changes slightly by provider:

- **OpenAI** exposes **Reasoning effort** with `none`, `low`, `medium`, and `high`.
- **Anthropic** exposes **Adaptive thinking**.
- **Gemini** exposes **Thinking level** with `low`, `medium`, and `high`.

These controls are translated into the normalized request model while provider construction stays isolated behind the application service.

---

## 8. Clear the Session

The two clear operations have different purposes:

- **Clear** removes the current prompt and generated-response state.
- **Clear all session credentials** returns the application to its zero-key state.

Before leaving the application, especially on a shared computer:

1. Open **Manage API Keys**.
2. Press **Clear all session credentials**.
3. Confirm the zero-key state.
4. Close the browser tab.

---

## 9. Common Problems

### No credential is authorized

Open **Manage API Keys**, enter a key for the selected provider, and press **Authorize entered keys for this session**.

### The application asks for a prompt

The prompt field is empty. Enter text before pressing **Generate response**.

### The application asks for a model name

The **Model** field is empty. Enter a valid model name for the selected provider.

### The provider request fails unexpectedly

Check:

1. the authorized credential,
2. the selected provider,
3. the model name,
4. the network connection,
5. provider-side access, quota, or billing restrictions.

The application reports provider failures instead of presenting them as successful execution.

### The default model is unavailable

Replace the **Model** value with a model currently available to your provider account.

---

## 10. Run the Verification Suite

From the repository root:

```powershell
uv run pytest
```

The configured repository suite includes the Module 1 tests under `module-01/tests/`.

The accepted Module 1 completion record reports 84 automated tests together with credential, provider, rate-limit, token-cost, queue, Postman, streaming, runtime, and live-provider verification.

---

## 11. Suggested 5-Minute Reviewer Path

For a quick technical review:

1. Launch the Streamlit application.
2. Confirm the zero-key state.
3. Attempt one request without a credential and confirm it is denied.
4. If you have a provider key, authorize it for the session.
5. Run one non-streaming request.
6. Inspect **Normalized Metadata**.
7. Run one streaming request.
8. Clear all session credentials.

That sequence demonstrates the central Module 1 behaviors: explicit credential authorization, provider-independent requests, normalized responses, token accounting, streaming, and fail-safe user-visible error handling.

---

## 12. What to Look For

A successful review should make these properties visible:

- The application starts without provider authority.
- Credentials require explicit session authorization.
- OpenAI, Anthropic, and Gemini share one application-facing service contract.
- Provider-specific reasoning controls remain bounded to provider configuration.
- Non-streaming responses expose normalized token metadata.
- Streaming responses render incrementally.
- Invalid or missing inputs are rejected visibly.
- Provider failures are not presented as successful execution.
- Session credentials can be explicitly cleared.

---

## 13. Go Deeper

- [Module 1 README](../README.md)
- [`app.py`](../app.py)
- [`src/ai_engineering_foundations/`](../src/ai_engineering_foundations/)
- [`tests/`](../tests/)
- [Postman collection](../postman/module-01-rest-api-foundations.postman_collection.json)
