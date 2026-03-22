# LLM Chatbot for Demand Parameters Modification

## 1. Purpose
Enable non-technical users to modify complex demand parameters (e.g. baseline, seasonal peaks, standard deviation) using natural language. The chatbot serves as an intelligent assistant that understands business goals (e.g., "increase summer demand by 20% and add a new festival spike in December") and translates them into precise parameter changes.

## 2. Tone & Aesthetic direction
**Industrial Utilitarian**
Consistent with the existing frontend aesthetic (Replenix). The widget will emphasize function, using monospace fonts for data points, high-contrast borders (border-border/50), minimal styling, and a terminal/console-like interaction feel rather than a typical "bubbly" consumer chatbot.

## 3. Differentiation Anchor
"If this were screenshotted with the logo removed, how would someone recognize it?"
The chatbot interface will look like an industrial command terminal floating over the data dashboard, featuring a raw, modular structure with distinct parameter-diff previews before applying changes.

## 4. Architecture & Data Flow
**Backend (FastAPI)**
- Endpoint: `POST /api/demand/chat-modify`
- The endpoint securely holds the Gemini API key (supplied via environment variable `GEMINI_API_KEY`).
- Payload from frontend: `{ "message": "increase baseline to 500", "current_params": { ...DetectedParams } }`.
- Backend calls Gemini Flash using the official `google-genai` or `google-generativeai` package.
- The prompt provided to Gemini will instruct it to return ONLY a JSON object representing the *modifications* to make to the current parameters, along with a short conversational reply.
- Backend merges the changes and returns: `{ "reply": string, "updated_params": { ...DetectedParams } }`.

**Frontend (React/Vite)**
- Component: `DemandChatWidget` located in `ModifyDemand.tsx`.
- UI: A floating, collapsible panel in the bottom-right.
- It displays the chat history (user commands and AI confirmations).
- When a new set of parameters is returned by the backend, the frontend immediately updates the React state (`setParams`) and triggers a graph refresh.

## 5. Components
1. **ChatWidget Container**: Manages open/close state, floating positioning.
2. **MessageList**: Displays alternating user and system messages. Uses monospace fonts for parameter changes explicitly highlighted in the UI.
3. **InputArea**: Text input with a submit button (lucide-react icons, minimal UI).

## 6. Error Handling
- **LLM parsing failure**: If Gemini returns invalid JSON, the backend catches the error and returns a friendly message: "I couldn't understand that modification. Could you rephrase it?"
- **Network failure**: Handled by the existing `handleResponse` utility in `api.ts`, showing a toast notification.
- **Unclear requests**: The prompt to Gemini will instruct it that if a request doesn't map to the available parameters, it should ask the user for clarification instead of guessing wildly.

## 7. Testing Strategy
- **Manual Verification**: 
  1. Open the `/modify` page.
  2. Open the chatbot widget.
  3. Type "increase the baseline average demand to 1000".
  4. Verify the backend successfully calls Gemini.
  5. Verify the frontend graph updates and the "Avg. Daily Demand" input changes to 1000.
