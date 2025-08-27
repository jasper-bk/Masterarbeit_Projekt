# portfolio_ai.py
#!/usr/bin/env python3

from datetime import datetime, date, timedelta, timezone

from portfolio_ai import PortfolioAIAssistant, Portfolio

from typing import Dict, List, Optional, Any, Tuple, Callable, Iterable

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# LangChain message history & wrappers
try:
    from langchain_core.runnables.history import RunnableWithMessageHistory
    from langchain_core.chat_history import InMemoryChatMessageHistory, BaseChatMessageHistory
    from langchain_core.prompts import MessagesPlaceholder
except Exception as _e:
    RunnableWithMessageHistory = None
    InMemoryChatMessageHistory = None
    BaseChatMessageHistory = None
    MessagesPlaceholder = None

# Optional RAG dependencies
try:
    from langchain_community.vectorstores import FAISS  # pip install faiss-cpu (or faiss-gpu)
except Exception:
    FAISS = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:
    # fallback splitter
    RecursiveCharacterTextSplitter = None

# Embeddings (try multiple providers depending on environment)
try:
    from langchain_ollama import OllamaEmbeddings
except Exception:
    OllamaEmbeddings = None

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    OpenAIEmbeddings = None

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except Exception:
    GoogleGenerativeAIEmbeddings = None


def build_chat_context_from_portfolio(portfolio: Portfolio, include_derived: bool = True, max_chars: int = 60_000) -> str:
    """
    Build a compact JSON context string directly from the Portfolio object.
    Optionally include derived values (quantity, average buy-in, holding days, current yield).
    The output is hard-limited to `max_chars` to avoid overly large prompts.
    """
    base = portfolio.to_dict()  # persistent fields

    if include_derived:
        derived_assets: Dict[str, Dict[str, Any]] = {}
        for t, a in portfolio.assets.items():
            # Try to pull a "current" price if you store it in evaluation_results
            last_eval = (a.evaluation_results or {})
            current_price = None
            try:
                current_price = last_eval.get("current_price")
            except Exception:
                current_price = None

            ctx = {
                "total_quantity": a.total_quantity(),
                "total_cost": a.total_cost(),
                "avg_buy_in": a.average_buy_in(),
                "first_purchase_date": a.first_purchase_date().isoformat() if a.first_purchase_date() else None,
                "holding_days": a.holding_days(),
            }
            y = a.current_yield(current_price) if current_price else None
            if current_price is not None:
                ctx["current_price"] = current_price
            if y is not None:
                ctx["current_yield"] = y

            derived_assets[t] = ctx

        base["_derived"] = {
            "assets": derived_assets,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    try:
        s = json.dumps(base, ensure_ascii=False, indent=2)
    except Exception:
        s = str(base)

    if len(s) > max_chars:
        s = s[:max_chars] + "\n... [truncated]"
    return s


class PortfolioChat:
    """
    Stateful chat over a Portfolio object with LangChain:
      - Multiple parallel sessions via session_id
      - In-memory history per session; history can be cleared
      - Optional RAG (FAISS) over the portfolio JSON context
      - Uses the same LLM as PortfolioAIAssistant.chat (pass the assistant at init)

    Example:
        assistant = PortfolioAIAssistant(provider="ollama", model="qwen3:14b")
        pf = assistant.new_portfolio("Demo", "Goals ...")
        chat = PortfolioChat(assistant, pf, use_rag=True)
        reply = chat.ask("sess-123", "What do you think about MBG.DE?")
        chat.clear("sess-123")
    """

    def __init__(
        self,
        assistant: PortfolioAIAssistant,
        portfolio: Portfolio,
        use_rag: bool = True,
        embeddings_provider: Optional[str] = None,   # "ollama" | "openai" | "google" | None (auto)
        ollama_emb_model: str = "nomic-embed-text",
        openai_emb_model: str = "text-embedding-3-small",
        google_emb_model: str = "models/embedding-001",
        k_retrieval: int = 6,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
    ):
        if RunnableWithMessageHistory is None or InMemoryChatMessageHistory is None or MessagesPlaceholder is None:
            raise ImportError(
                "LangChain core history modules not available. "
                "Ensure `langchain-core>=0.2` is installed."
            )

        self.assistant = assistant
        self.portfolio = portfolio
        self.use_rag = use_rag
        self.k_retrieval = k_retrieval
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._histories: Dict[str, BaseChatMessageHistory] = {}

        # Prompt (with history placeholder)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system",
                 "You are a disciplined investment assistant. "
                 "Use the provided portfolio context and retrieved snippets if available. "
                 "Be concise, do not hallucinate figures absent from context. "
                 "If information is missing, say so and propose a next step.\n\n"
                 "PORTFOLIO CONTEXT (may be truncated):\n{portfolio_context}\n\n"
                 "RETRIEVED SNIPPETS (if any):\n{retrieved}\n"),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ]
        )

        # LCEL chain
        self._base_chain = self._prompt | self.assistant.chat | StrOutputParser()

        # Wrapped chain with message history
        self._chain = RunnableWithMessageHistory(
            self._base_chain,
            self._get_history_for_session,
            input_messages_key="input",
            history_messages_key="history",
        )

        # Optional vector index (RAG)
        self._emb_provider = embeddings_provider
        self._embeddings = self._init_embeddings(embeddings_provider, ollama_emb_model, openai_emb_model, google_emb_model)
        self._vectorstore = None
        if self.use_rag and self._embeddings and FAISS:
            try:
                self._vectorstore = self._build_vectorstore()
            except Exception as e:
                print(f"[RAG] Failed to build vectorstore: {e}")
                self._vectorstore = None
        elif self.use_rag:
            print("[RAG] Vectorstore disabled (FAISS/Embeddings not available).")

    # --------- Public API ---------
    def ask(self, session_id: str, user_message: str) -> str:
        """
        Ask a question within the chat context (with history).
        Returns the LLM answer as a string.
        """
        portfolio_ctx = build_chat_context_from_portfolio(self.portfolio, include_derived=True)

        retrieved_text = ""
        if self.use_rag and self._vectorstore:
            try:
                retriever = self._vectorstore.as_retriever(search_kwargs={"k": self.k_retrieval})
                docs = retriever.get_relevant_documents(user_message)
                retrieved_text = "\n\n".join([f"- {d.page_content}" for d in docs])[:8000]
            except Exception as e:
                print(f"[RAG] Retrieval failed: {e}")
                retrieved_text = ""

        # invoke with history
        result = self._chain.invoke(
            {"input": user_message, "portfolio_context": portfolio_ctx, "retrieved": retrieved_text},
            config={"configurable": {"session_id": session_id}},
        )
        return result

    def clear(self, session_id: str) -> None:
        """
        Clear the chat history for a given session.
        """
        if session_id in self._histories:
            self._histories.pop(session_id, None)

    def get_history(self, session_id: str) -> Iterable[Dict[str, str]]:
        """
        Return the history as a simple list of {role, content}.
        """
        hist = self._histories.get(session_id)
        out = []
        if not hist:
            return out
        for m in hist.messages:
            role = getattr(m, "type", None) or getattr(m, "role", "") or m.__class__.__name__
            content = getattr(m, "content", "")
            out.append({"role": role, "content": content})
        return out

    # --------- Internals ---------
    def _get_history_for_session(self, session_id: str) -> BaseChatMessageHistory:
        if session_id not in self._histories:
            self._histories[session_id] = InMemoryChatMessageHistory()
        return self._histories[session_id]

    def _init_embeddings(
        self,
        provider: Optional[str],
        ollama_model: str,
        openai_model: str,
        google_model: str,
    ):
        """
        Initialize an embedding model depending on environment.
        """
        prov = (provider or self.assistant.provider or "").lower()

        # explicit provider choice
        if prov == "ollama" and OllamaEmbeddings is not None:
            return OllamaEmbeddings(model=ollama_model, base_url=self.assistant.ollama_base_url)
        if prov == "openai" and OpenAIEmbeddings is not None:
            if not self.assistant.openai_api_key:
                print("[RAG] OPENAI_API_KEY missing; falling back.")
            else:
                return OpenAIEmbeddings(model=openai_model, api_key=self.assistant.openai_api_key)
        if prov in ("google", "gemini") and GoogleGenerativeAIEmbeddings is not None:
            if not self.assistant.google_api_key:
                print("[RAG] GOOGLE_API_KEY missing; falling back.")
            else:
                return GoogleGenerativeAIEmbeddings(model=google_model, google_api_key=self.assistant.google_api_key)

        # auto selection
        if OllamaEmbeddings is not None:
            return OllamaEmbeddings(model=ollama_model, base_url=self.assistant.ollama_base_url)
        if OpenAIEmbeddings is not None and self.assistant.openai_api_key:
            return OpenAIEmbeddings(model=openai_model, api_key=self.assistant.openai_api_key)
        if GoogleGenerativeAIEmbeddings is not None and self.assistant.google_api_key:
            return GoogleGenerativeAIEmbeddings(model=google_model, google_api_key=self.assistant.google_api_key)

        print("[RAG] No embeddings available; RAG disabled.")
        return None

    def _build_vectorstore(self):
        """
        Build a FAISS vector index over the entire portfolio (including derived values).
        """
        if FAISS is None or not self._embeddings:
            return None

        text = build_chat_context_from_portfolio(self.portfolio, include_derived=True, max_chars=200_000)

        # Split
        if RecursiveCharacterTextSplitter:
            splitter = RecursiveCharacterTextSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
            chunks = splitter.split_text(text)
        else:
            # very simple fallback split strategy
            chunks = []
            step = self.chunk_size
            for i in range(0, len(text), step - self.chunk_overlap):
                chunks.append(text[i:i + step])

        # Load into FAISS
        try:
            vs = FAISS.from_texts(chunks, self._embeddings)
            return vs
        except Exception as e:
            print(f"[RAG] Building FAISS failed: {e}")
            return None


# ----------------------------- Minimal usage example (optional) -----------------------------
if __name__ == "__main__":
    assistant = PortfolioAIAssistant(provider="ollama", model="qwen3:14b")
    pf = assistant.new_portfolio("Sample", "Long-term growth / balanced risk")
    pf.add_asset("MBG.DE", name="Mercedes-Benz Group")
    pf.add_trade("MBG.DE", 10, 50.10, "2023-05-01")

    chat = PortfolioChat(assistant, pf, use_rag=True)  # RAG optional
    session_id = "user-123"

    print(chat.ask(session_id, "Gib mir einen kurzen Überblick über mein Portfolio."))
    print(chat.ask(session_id, "Und speziell zu MBG.DE – wie ist die Lage?"))

    # Verlauf löschen
    chat.clear(session_id)
    print(chat.ask(session_id, "Woran soll ich als Nächstes arbeiten?"))