# portfolio_ai.py
#!/usr/bin/env python3

"""
PortfolioAIAssistant + Portfolio model
- All AI logic via LangChain (LCEL, structured outputs, optional ensemble)
- LLM providers: OpenAI, Ollama, Anthropic (Claude), Google (Gemini)
- Finance providers: yfinance, Finnhub (via finnhub-python SDK)
- Portfolio/Asset classes with trades; CRUD; save/load JSON (file/string)
- No derived values are stored (e.g., holding_days, current_yield). We compute them on the fly.
- We persist LLM prompts used for traceability:
    * Per-asset: evaluation_results.prompts = { llm_brief_prompt, assessment_messages }
    * Portfolio summary: portfolio_evaluation_results.prompts = { portfolio_summary_messages }
- Public methods kept compatible:
    * generate_response(prompt: str) -> str
    * evaluate_portfolio(portfolio, specific_assets=None) -> Dict
"""

import os
import re
import json
import time
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
import dotenv

# --- Finance providers ---
try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import finnhub  # pip install finnhub-python
except ImportError:
    finnhub = None

# --- LangChain core ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.runnables import RunnableParallel

# --- Pydantic v2 ---
from pydantic import BaseModel, Field, ValidationError

# --- LangChain providers ---
try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except Exception:
    ChatAnthropic = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:
    ChatGoogleGenerativeAI = None

try:
    from langchain_ollama import ChatOllama
except Exception:
    ChatOllama = None

dotenv.load_dotenv()

# ============================================================
# Portfolio data model (no derived values stored)
# ============================================================

class Asset:
    """
    Represents a single security with trades and evaluation state.
    Persistent fields only:
      - name (optional)
      - trades: list of { "quantity": float, "price": float, "date": "YYYY-MM-DD" }
      - evaluation_results: dict (empty until first LLM evaluation)
    """
    def __init__(self, ticker: str, name: Optional[str] = None):
        self.ticker = ticker
        self.name = name
        self.trades: List[Dict[str, Any]] = []
        self.evaluation_results: Dict[str, Any] = {}  # empty until evaluated

    # ---------- CRUD for trades ----------
    def add_trade(self, quantity: float, price: float, date_str: str):
        """
        Adds a trade. Use negative quantity for sells if needed.
        date_str must be ISO format (YYYY-MM-DD).
        """
        self.trades.append({
            "quantity": float(quantity),
            "price": float(price),
            "date": date_str
        })

    def clear_trades(self):
        self.trades = []

    def set_name(self, name: Optional[str]):
        self.name = name

    # ---------- Derived computations (not stored) ----------
    def total_quantity(self) -> float:
        return sum(float(t["quantity"]) for t in self.trades)

    def total_cost(self) -> float:
        # Cost basis (buys positive, sells negative if quantity < 0)
        return sum(float(t["quantity"]) * float(t["price"]) for t in self.trades)

    def average_buy_in(self) -> Optional[float]:
        qty = self.total_quantity()
        if qty <= 0:
            return None
        cost = self.total_cost()
        return cost / qty if qty else None

    def first_purchase_date(self) -> Optional[date]:
        if not self.trades:
            return None
        try:
            dts = [
                datetime.fromisoformat(t["date"]).date()
                for t in self.trades
                if t.get("date")
            ]
            return min(dts) if dts else None
        except Exception:
            return None

    def holding_days(self, asof: Optional[date] = None) -> Optional[int]:
        if asof is None:
            asof = date.today()
        start = self.first_purchase_date()
        if not start:
            return None
        return (asof - start).days

    def current_yield(self, current_price: Optional[float]) -> Optional[float]:
        """
        Simple return based on average buy-in (ignores dividends/fees).
        """
        if not current_price:
            return None
        avg = self.average_buy_in()
        if not avg or avg == 0:
            return None
        return (current_price - avg) / avg

    # ---------- Evaluation results ----------
    def set_evaluation_results(self, results: Dict[str, Any]):
        """
        Stores LLM evaluation results and stamps last evaluation time.
        """
        results = dict(results or {})
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        results["last_evaluated_at"] = ts
        self.evaluation_results = results

    def clear_evaluation(self):
        self.evaluation_results = {}

    # ---------- Serialization ----------
    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": self.name,
            "trades": self.trades,
            "evaluation_results": self.evaluation_results
        }
        # drop None name to keep JSON minimal
        if data["name"] is None:
            del data["name"]
        return data

    @classmethod
    def from_dict(cls, ticker: str, data: Dict[str, Any]) -> "Asset":
        a = cls(ticker=ticker, name=data.get("name"))
        for t in data.get("trades", []):
            a.add_trade(
                quantity=t.get("quantity", 0.0),
                price=t.get("price", 0.0),
                date_str=t.get("date", date.today().isoformat())
            )
        a.evaluation_results = dict(data.get("evaluation_results", {}))
        return a


class Portfolio:
    """
    Represents a portfolio of assets.
    Persistent fields:
      - portfolio_name
      - investor_goals
      - assets: { ticker: Asset }
      - portfolio_evaluation_results (optional; empty until evaluated)
    """
    def __init__(self, portfolio_name: str, investor_goals: str = ""):
        self.portfolio_name = portfolio_name
        self.investor_goals = investor_goals
        self.assets: Dict[str, Asset] = {}
        self.portfolio_evaluation_results: Dict[str, Any] = {}

    # ---------- Asset CRUD ----------
    def add_asset(self, ticker: str, name: Optional[str] = None) -> Asset:
        ticker = ticker.upper()
        if ticker not in self.assets:
            self.assets[ticker] = Asset(ticker=ticker, name=name)
        else:
            if name is not None:
                self.assets[ticker].set_name(name)
        return self.assets[ticker]

    def remove_asset(self, ticker: str) -> bool:
        ticker = ticker.upper()
        return self.assets.pop(ticker, None) is not None

    def update_asset_name(self, ticker: str, name: Optional[str]) -> None:
        self.add_asset(ticker).set_name(name)

    def add_trade(self, ticker: str, quantity: float, price: float, date_str: str) -> None:
        self.add_asset(ticker).add_trade(quantity, price, date_str)

    def clear_asset_trades(self, ticker: str) -> None:
        if ticker.upper() in self.assets:
            self.assets[ticker.upper()].clear_trades()

    def clear_asset_evaluation(self, ticker: str) -> None:
        if ticker.upper() in self.assets:
            self.assets[ticker.upper()].clear_evaluation()

    def get_all_tickers(self) -> List[str]:
        return list(self.assets.keys())

    # ---------- Serialization (portfolio) ----------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_name": self.portfolio_name,
            "investor_goals": self.investor_goals,
            "assets": {t: a.to_dict() for t, a in self.assets.items()},
            **({"portfolio_evaluation_results": self.portfolio_evaluation_results}
               if self.portfolio_evaluation_results else {})
        }

    def to_json_str(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_to_file(self, path: str, indent: int = 2) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json_str(indent=indent))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        p = cls(
            portfolio_name=data.get("portfolio_name", "Unnamed Portfolio"),
            investor_goals=data.get("investor_goals", "")
        )
        assets = data.get("assets", {})
        for ticker, a_data in assets.items():
            p.assets[ticker.upper()] = Asset.from_dict(ticker.upper(), a_data or {})
        p.portfolio_evaluation_results = dict(data.get("portfolio_evaluation_results", {}))
        return p

    @classmethod
    def from_json_str(cls, s: str) -> "Portfolio":
        return cls.from_dict(json.loads(s))

    @classmethod
    def load_from_file(cls, path: str) -> "Portfolio":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json_str(f.read())

    # ---------- Serialization (single asset) ----------
    def asset_to_json_str(self, ticker: str, indent: int = 2) -> str:
        a = self.assets.get(ticker.upper())
        if not a:
            raise KeyError(f"Asset '{ticker}' not found.")
        return json.dumps(a.to_dict(), ensure_ascii=False, indent=indent)

    def upsert_asset_from_json_str(self, ticker: str, s: str) -> None:
        data = json.loads(s)
        self.assets[ticker.upper()] = Asset.from_dict(ticker.upper(), data)


# ============================================================
# LLM structured outputs for evaluation
# ============================================================

class SecurityAssessment(BaseModel):
    urgency_to_act: int = Field(..., ge=0, le=100)
    buy: int = Field(..., ge=0, le=100)
    sell: int = Field(..., ge=0, le=100)
    hold: int = Field(..., ge=0, le=100)
    potential_upside: int = Field(0, ge=0, le=100)
    potential_downside: int = Field(0, ge=0, le=100)
    rationale: str

    def validate_sum(self) -> None:
        total = int(self.buy) + int(self.sell) + int(self.hold)
        if abs(total - 100) > 1:
            raise ValueError(f"buy+sell+hold must sum to 100 (+/-1), got {total}.")


class PortfolioSummary(BaseModel):
    market_summary: str
    current_opportunities: str
    current_risks: str
    other: str
    explanation_evaluation: str


# ============================================================
# Assistant
# ============================================================

class PortfolioAIAssistant:
    """
    Unified assistant with traceable prompts:
      - All LLM interactions via LangChain.
      - Optional ensemble across multiple providers.
      - Pluggable finance data sources (yfinance, Finnhub via SDK).
      - Public methods kept compatible:
          * generate_response(prompt: str) -> str
          * evaluate_portfolio(portfolio, specific_assets=None) -> Dict
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "deepseek-r1:14b",
        temperature: float = 0,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = 60,
        ensemble: bool = False,
        ensemble_providers: Optional[List[Dict[str, str]]] = None,
        ensemble_merge: str = "synthesis",
        finance_provider: str = "yfinance",       # "yfinance" | "finnhub"
        finnhub_api_key: Optional[str] = None,
        finnhub_days_back: int = 21,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        user_response_preferences : Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        self.ensemble = ensemble
        self.ensemble_providers = ensemble_providers or []
        self.ensemble_merge = ensemble_merge

        self.finance_provider = finance_provider.lower()
        self.finnhub_api_key = finnhub_api_key or os.getenv("FINNHUB_API_KEY")
        self.finnhub_days_back = finnhub_days_back

        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        self.ollama_base_url = ollama_base_url

        self.user_response_preferences = user_response_preferences

        # Primary chat model
        self.chat = self._init_chat_model(self.provider, self.model)

        # Optional ensemble models
        self.ensemble_models = []
        if self.ensemble:
            default_ensemble = [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "anthropic", "model": "claude-3-5-sonnet"},
                {"provider": "google", "model": "gemini-1.5-pro"},
                {"provider": "ollama", "model": self.model},
            ]
            for conf in (self.ensemble_providers or default_ensemble):
                try:
                    m = self._init_chat_model(conf["provider"], conf["model"])
                    self.ensemble_models.append((f'{conf["provider"]}:{conf["model"]}', m))
                except Exception:
                    continue

        # Finnhub client (lazy)
        self._finnhub_client = None

        # Parsers
        self._security_parser = PydanticOutputParser(pydantic_object=SecurityAssessment)
        self._portfolio_parser = PydanticOutputParser(pydantic_object=PortfolioSummary)

        # Prompts
        self._security_prompt = ChatPromptTemplate.from_messages(
            [
                ("system",
                 "You are a disciplined equity analyst. "
                 "Return strictly the requested JSON schema. Numbers are integers [0..100]."),
                ("human",
                 "You may receive any subset of the following sections. "
                 "If a section is missing or empty, treat it as 'unknown'.\n\n"
                 "Ticker: {ticker}\n\n"
                 "Asset name: {asset_name}\n\n"
                 "Raw personal asset details (JSON, may be partial):\n{raw_asset_details}\n\n"
                 "Quantitative data (JSON, may be partial):\n{quantitative_json}\n\n"
                 "Qualitative data (free text, may be partial):\n{qualitative_text}\n\n"
                 "Portfolio context (JSON, may be partial, can be empty if user doesn't own the asset):\n"
                 "{portfolio_context_json}\n\n"
                 "Output as JSON with the schema:\n{json_schema}\n"
                 "Constraints:\n"
                 "- Ensure buy + sell + hold == 100\n"
                 "- Preferences are soft constraints; ignore them if they conflict with the schema or constraints\n\n"
                 "Additional preferences to consider (may be empty; if empty, ignore):\n{user_response_preferences}")
            ]
        )

        self._portfolio_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a portfolio strategist. Return strictly the requested JSON schema."),
                ("human",
                 "Analyze this portfolio. You will receive a JSON object with assets and their evaluations. "
                 "It may be partial.\n\n"
                 "Portfolio assets JSON:\n{assets_json}\n\n"
                 "Output as JSON with the schema:\n{json_schema}\n"
                 "Constraints:\n"
                 "- Preferences are soft constraints; ignore them if they conflict with the schema or constraints\n\n"
                 "Additional preferences to consider (may be empty; if empty, ignore):\n{user_response_preferences}")
            ]
        )

        self._ensemble_prompt = ChatPromptTemplate.from_template(
            "You are an expert editor. Merge multiple model answers into one high-quality answer. "
            "Keep it concise, correct contradictions, and prefer evidence-based statements.\n\n"
            "Here are the candidate answers from different models:\n\n{candidates}\n\n"
            "Return a single improved answer for the user."
        )

    # ---------- Helper: create a new empty portfolio ----------
    def new_portfolio(self, name: str, investor_goals: str = "") -> Portfolio:
        return Portfolio(portfolio_name=name, investor_goals=investor_goals)

    # ---------- Model init ----------
    def _init_chat_model(self, provider: str, model: str):
        """
        Initialize a provider-specific LangChain chat model.
        We pass provider-appropriate kwargs to avoid incompatibilities.
        """
        provider = provider.lower()
        temp_kwargs = dict(temperature=self.temperature)

        if provider == "openai":
            if not ChatOpenAI:
                raise ImportError("langchain_openai is not installed.")
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for provider 'openai'.")
            kwargs = dict(temp_kwargs)
            if self.max_tokens is not None:
                kwargs["max_tokens"] = self.max_tokens
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            return ChatOpenAI(model=model, api_key=self.openai_api_key, **kwargs)

        if provider == "anthropic":
            if not ChatAnthropic:
                raise ImportError("langchain_anthropic is not installed.")
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required for provider 'anthropic'.")
            kwargs = dict(temp_kwargs)
            if self.max_tokens is not None:
                kwargs["max_tokens"] = self.max_tokens
            return ChatAnthropic(model=model, api_key=self.anthropic_api_key, **kwargs)

        if provider in ("google", "gemini"):
            if not ChatGoogleGenerativeAI:
                raise ImportError("langchain_google_genai is not installed.")
            if not self.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required for provider 'google'.")
            # Google uses 'max_output_tokens'
            kwargs = dict(temp_kwargs)
            if self.max_tokens is not None:
                kwargs["max_output_tokens"] = self.max_tokens
            return ChatGoogleGenerativeAI(model=model, google_api_key=self.google_api_key, **kwargs)

        if provider == "ollama":
            if not ChatOllama:
                raise ImportError("langchain_ollama is not installed.")
            # Ollama wrapper typically doesn't accept 'max_tokens'; keep it simple
            kwargs = dict(temp_kwargs)
            return ChatOllama(model=model, base_url=self.ollama_base_url, **kwargs)

        raise ValueError(f"Unsupported provider: {provider}")

    # ============================================================
    # Public API (unchanged): generate_response
    # ============================================================
    def generate_response(self, prompt: str) -> str:
        """
        If ensemble is enabled, run multiple models in parallel and synthesize.
        Otherwise, run the primary model. Always returns a string.
        """
        try:
            if not self.ensemble or not self.ensemble_models:
                chain = ChatPromptTemplate.from_messages(
                    [("system", "You are a helpful assistant."), ("human", "{prompt}")]
                ) | self.chat | StrOutputParser()
                return chain.invoke({"prompt": prompt})

            rp = RunnableParallel(
                **{name: (ChatPromptTemplate.from_messages([
                        ("system", "You are a helpful assistant."), ("human", "{prompt}")
                    ]) | model | StrOutputParser())
                   for name, model in self.ensemble_models}
            )
            candidates: Dict[str, str] = rp.invoke({"prompt": prompt})

            if self.ensemble_merge == "concat":
                return "\n\n".join([f"### {k}\n{v}" for k, v in candidates.items()])

            synth_chain = self._ensemble_prompt | self.chat | StrOutputParser()
            return synth_chain.invoke({"candidates": json.dumps(candidates, indent=2)})

        except Exception as e:
            try:
                msg = f"(Note: ensemble failed: {e}. Falling back to single model.)\n\n{prompt}"
                chain = ChatPromptTemplate.from_messages(
                    [("system", "You are a helpful assistant."), ("human", "{prompt}")]
                ) | self.chat | StrOutputParser()
                return chain.invoke({"prompt": msg})
            except Exception as e2:
                return f"Error generating response: {e2}"

    # ============================================================
    # Finance data access (Finnhub via SDK, yfinance fallback)
    # ============================================================
    def _ensure_finnhub(self):
        if self._finnhub_client is None:
            if finnhub is None:
                raise ImportError("finnhub-python is not installed. Run: pip install finnhub-python")
            if not self.finnhub_api_key:
                raise ValueError("FINNHUB_API_KEY required for finance_provider='finnhub'.")
            self._finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
        return self._finnhub_client

    def get_quantitative_data(self, identifier: str) -> Dict[str, Any]:
        t0 = time.time()
        try:
            if self.finance_provider == "finnhub":
                fh = self._ensure_finnhub()
                q = fh.quote(identifier)  # {'c','h','l','o','pc','t'}
                bf = fh.company_basic_financials(identifier, 'all')  # {'metric': {...}}
                metrics = (bf or {}).get("metric", {}) if isinstance(bf, dict) else {}

                return {
                    "current_price": q.get("c"),
                    "open_price": q.get("o"),
                    "day_high": q.get("h"),
                    "day_low": q.get("l"),
                    "prev_close": q.get("pc"),
                    "pe_ratio": metrics.get("peNormalizedAnnual") or metrics.get("peTTM"),
                    "market_cap": metrics.get("marketCapitalization"),
                }

            # Default: yfinance
            if yf is None:
                raise ImportError("yfinance not installed. Install or switch to 'finnhub'.")
            t = yf.Ticker(identifier)
            info = {}
            try:
                info = t.info
            except Exception:
                info = {}
            fast = getattr(t, "fast_info", None)
            fast_price = getattr(fast, "last_price", None) if fast else None
            return {
                "current_price": info.get("currentPrice", fast_price),
                "pe_ratio": info.get("trailingPE"),
                "market_cap": info.get("marketCap"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "open_price": info.get("open"),
                "prev_close": info.get("previousClose"),
            }
        except Exception as e:
            print(f"[Error] Quantitative data for {identifier}: {e}")
            return {}
        finally:
            print(f"Getting quantitative data for {identifier} took {time.time() - t0:.2f}s")

    # ============================================================
    # Qualitative data + prompt capture
    # ============================================================
    def get_qualitative_data(self, identifier: str, asset_name : Optional[str] = None) -> Tuple[str, str]:
        """
        Returns (qualitative_text, llm_brief_prompt).
        """
        try:
            if asset_name:
                llm_text, llm_prompt = self._get_llm_analysis(asset_name)
            else:
                llm_text, llm_prompt = self._get_llm_analysis(identifier)
        except Exception as e:
            llm_text = f"(LLM pre-brief failed: {e})"
            llm_prompt = f"Give a concise business overview, recent events, and key risks/opportunities for {identifier}."

        provider_notes = ""
        try:
            if self.finance_provider == "finnhub":
                fh = self._ensure_finnhub()
                prof = fh.company_profile2(symbol=identifier)  # {'name','exchange','finnhubIndustry','weburl',...}
                profile_txt = ""
                if prof:
                    profile_txt = (
                        f"Name: {prof.get('name')} — Exchange: {prof.get('exchange')} — "
                        f"Industry: {prof.get('finnhubIndustry')} — Web: {prof.get('weburl')}"
                    )
                end = date.today()
                start = end - timedelta(days=self.finnhub_days_back)
                news = fh.company_news(identifier, _from=start.isoformat(), to=end.isoformat())
                top_news = []
                if isinstance(news, list):
                    for item in news[:5]:
                        ds = item.get("datetime")
                        # finnhub returns ISO8601 str or int epoch depending on endpoint version; handle both
                        if isinstance(ds, (int, float)):
                            ds = datetime.fromtimestamp(ds).date().isoformat()
                        elif isinstance(ds, str):
                            ds = ds[:10]
                        else:
                            ds = "n/a"
                        top_news.append(f"- {item.get('headline')} ({item.get('source')}, {ds})")
                news_txt = "\n".join(top_news)
                provider_notes = f"PROFILE:\n{profile_txt}\n\nRECENT_NEWS:\n{news_txt}"
            else:
                if yf is None:
                    raise ImportError("yfinance not installed.")
                t = yf.Ticker(identifier)
                info = {}
                try:
                    info = t.info
                except Exception:
                    pass
                long_summary = info.get("longBusinessSummary") or ""
                sector = info.get("sector") or ""
                industry = info.get("industry") or ""
                provider_notes = f"SUMMARY: {long_summary}\nSECTOR: {sector} — INDUSTRY: {industry}"
        except Exception as e:
            provider_notes = f"(Provider qualitative fetch failed: {e})"

        qualitative_text = f"LLM_BRIEF:\n{llm_text}\n\nPROVIDER_CONTEXT:\n{provider_notes}"
        return qualitative_text, llm_prompt

    def _get_llm_analysis(self, identifier: str) -> Tuple[str, str]:
        """
        Small pre-brief for qualitative context.
        Returns (text, prompt) so the caller can persist the prompt.
        """
        prompt = f"Give a concise business overview, recent events, and key risks/opportunities for {identifier}."
        t0 = time.time()
        out = self.generate_response(prompt)
        print(f"Getting LLM asset analysis for {identifier} took {time.time() - t0:.2f}s")
        return out, prompt

    # ============================================================
    # Internal helpers for structured assessment
    # ============================================================
    def _render_json(self, obj: Any) -> str:
        if not obj:
            return "{}"
        try:
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            return "{}"

    def _messages_to_dicts(self, messages: List[Any]) -> List[Dict[str, str]]:
        """
        Convert LangChain BaseMessage list to simple [{role, content}, ...] for persistence.
        """
        out: List[Dict[str, str]] = []
        for m in messages:
            role = getattr(m, "type", None) or getattr(m, "role", "") or m.__class__.__name__
            content = getattr(m, "content", "")
            out.append({"role": role, "content": content})
        return out

    def _build_asset_context_for_llm(self, asset: Asset, current_price: Optional[float]) -> Dict[str, Any]:
        """
        Build a compact, derived context for the LLM (NOT persisted).
        """
        qty = asset.total_quantity()
        avg = asset.average_buy_in()
        hold = asset.holding_days()
        yld = asset.current_yield(current_price)
        ctx = {
            "owns_asset": True if qty and qty > 0 else False,
            "quantity": qty if qty else 0,
            "avg_buy_in": round(avg, 6) if avg is not None else None,
            "first_purchase_date": asset.first_purchase_date().isoformat() if asset.first_purchase_date() else None,
            "holding_days": hold if hold is not None else None,
        }
        if current_price is not None:
            ctx["current_price"] = current_price
            if yld is not None:
                ctx["current_yield"] = yld
        return ctx

    def assess_security(self, security_data: Dict, portfolio_attributes: Dict) -> Dict:
        """
        Structured-output chain for per-security assessment.
        Returns the model fields plus a `prompts` key with rendered messages.
        """
        try:
            variables = {
                "ticker": security_data.get("ticker") or portfolio_attributes.get("ticker") or "UNKNOWN",
                "asset_name": security_data.get("asset_name") or "UNKNOWN",
                "raw_asset_details" : security_data.get("raw_asset_data"),
                "quantitative_json": self._render_json(security_data.get("quantitative")),
                "qualitative_text": security_data.get("qualitative", "") or "",
                "portfolio_context_json": self._render_json(portfolio_attributes or {}),
                "json_schema": self._security_parser.get_format_instructions(),
                "user_response_preferences": self.user_response_preferences
            }

            # Capture the exact messages sent to the model (for traceability)
            rendered_messages = self._security_prompt.format_messages(**variables)
            prompt_messages = self._messages_to_dicts(rendered_messages)

            try:
                model_structured = self.chat.with_structured_output(SecurityAssessment)
                result: SecurityAssessment = (self._security_prompt | model_structured).invoke(variables)
            except Exception:
                chain = self._security_prompt | self.chat | self._security_parser
                result: SecurityAssessment = chain.invoke(variables)


            result.validate_sum()
            out = result.model_dump()
            out["prompts"] = {"assessment_messages": prompt_messages}
            return out

        except (ValidationError, ValueError) as e:
            # Robust fallback: parse JSON from text; still persist the prompt
            print(f"[Warn] Structured parse failed, trying regex: {e}")
            rendered_messages = self._security_prompt.format_messages(
                ticker=security_data.get("ticker", "UNKNOWN"),
                quantitative_json=self._render_json(security_data.get("quantitative")),
                qualitative_text=security_data.get("qualitative", "") or "",
                portfolio_context_json=self._render_json(portfolio_attributes or {}),
                json_schema='{ "urgency_to_act": int, "buy": int, "sell": int, "hold": int, "potential_upside": int, "potential_downside": int, "rationale": str }',
            )
            prompt_messages = self._messages_to_dicts(rendered_messages)

            raw = (self._security_prompt | self.chat | StrOutputParser()).invoke(
                {
                    "ticker": security_data.get("ticker", "UNKNOWN"),
                    "quantitative_json": self._render_json(security_data.get("quantitative")),
                    "qualitative_text": security_data.get("qualitative", "") or "",
                    "portfolio_context_json": self._render_json(portfolio_attributes or {}),
                    "json_schema": '{ "urgency_to_act": int, "buy": int, "sell": int, "hold": int, "potential_upside": int, "potential_downside": int, "rationale": str }',
                }
            )
            m = re.search(r"({.*?})", raw, re.DOTALL)
            if not m:
                raise ValueError(f"No JSON found in response. Response: {raw}")
            parsed = json.loads(m.group(1))
            for k in ["urgency_to_act", "buy", "sell", "hold", "potential_upside", "potential_downside"]:
                parsed[k] = int(str(parsed.get(k, 0)).replace("%", "").strip() or 0)
            total = parsed["buy"] + parsed["sell"] + parsed["hold"]
            if abs(total - 100) > 1:
                raise ValueError(f"Percentages don't sum to 100. It is {total}")
            parsed["prompts"] = {"assessment_messages": prompt_messages}
            return parsed
        except Exception as e:
            print(f"[Error] Security assessment: {e}")
            return {
                "urgency_to_act": 0,
                "buy": 0,
                "sell": 0,
                "hold": 0,
                "potential_upside": 0,
                "potential_downside": 0,
                "rationale": f"Assessment failed or invalid format: {e}",
                "prompts": {"assessment_messages": []},
            }

    def evaluate_portfolio_summary(self, portfolio_dict: Dict) -> Dict:
        """
        Portfolio-level summary using structured output.
        Also persists the rendered prompt messages under 'prompts'.
        """
        print("Evaluating portfolio ...")
        try:
            variables = {
                "assets_json": self._render_json(portfolio_dict.get("assets", {})),
                "json_schema": self._portfolio_parser.get_format_instructions(),
                "user_response_preferences": self.user_response_preferences
            }
            rendered_messages = self._portfolio_prompt.format_messages(**variables)
            prompt_messages = self._messages_to_dicts(rendered_messages)

            try:
                model_structured = self.chat.with_structured_output(PortfolioSummary)
                result: PortfolioSummary = (self._portfolio_prompt | model_structured).invoke(variables)
            except Exception:
                chain = self._portfolio_prompt | self.chat | self._portfolio_parser
                result: PortfolioSummary = chain.invoke(variables)

            out = result.model_dump()
            out["prompts"] = {"portfolio_summary_messages": prompt_messages}
            return out
        except Exception as e:
            print(f"[Error] Portfolio summary: {e}")
            return {
                "market_summary": "N/A",
                "current_opportunities": "N/A",
                "current_risks": "N/A",
                "other": "N/A",
                "explanation_evaluation": f"Portfolio summary failed: {e}",
                "prompts": {"portfolio_summary_messages": []},
            }

    # ============================================================
    # Public API (unchanged): evaluate_portfolio
    # Accepts: dict or Portfolio instance. Returns dict (for backward compatibility).
    # ============================================================
    def evaluate_portfolio(self, portfolio, specific_assets=None) -> Dict:
        """
        Mutates evaluation results inside the provided portfolio (if Portfolio instance),
        and returns a dict representation (backward compatible).
        """
        # Normalize to Portfolio instance
        if isinstance(portfolio, Portfolio):
            p = portfolio
        elif isinstance(portfolio, dict):
            p = Portfolio.from_dict(portfolio)
        else:
            raise TypeError("portfolio must be a dict or Portfolio instance")

        portfolio_dict = p.to_dict()

        portfolio_assets_dict = portfolio_dict["assets"]

        tickers = portfolio_assets_dict.keys()

        if specific_assets:
            specific = {t.upper() for t in specific_assets}
            tickers = [t for t in tickers if t in specific]

        # Per-asset evaluation
        for ticker in tickers:

            print(f"Evaluating {ticker} ...")
            asset = p.assets[ticker]

            asset_dict = asset.to_dict()
            asset_name = asset_dict["name"]

            quant = self.get_quantitative_data(ticker)
            qual_text, llm_brief_prompt = self.get_qualitative_data(ticker, asset_name)

            # Derived, non-persistent context for the LLM:
            derived_ctx = self._build_asset_context_for_llm(
                asset=asset,
                current_price=quant.get("current_price")
            )

            security_data = {"ticker": ticker, "asset_name" : asset_name, "raw_asset_data" : asset_dict, "quantitative": quant, "qualitative": qual_text}

            t0 = time.time()
            assessment = self.assess_security(security_data=security_data, portfolio_attributes=derived_ctx)
            print(f"The LLM evaluation for {ticker} took {time.time() - t0:.2f}s")

            # Persist evaluation results with timestamp and prompts
            asset.set_evaluation_results({
                "urgency": assessment.get("urgency_to_act", 0),
                "buy": assessment.get("buy", 0),
                "sell": assessment.get("sell", 0),
                "hold": assessment.get("hold", 0),
                "potential_upside": assessment.get("potential_upside", 0),
                "potential_downside": assessment.get("potential_downside", 0),
                "explanation_evaluation": assessment.get("rationale", ""),
                "prompts": {
                    "llm_brief_prompt": llm_brief_prompt,
                    "assessment_messages": assessment.get("prompts", {}).get("assessment_messages", []),
                },
            })

        # Portfolio-level summary (also stores its prompt)
        p.portfolio_evaluation_results = self.evaluate_portfolio_summary(p.to_dict())

        # Return dict (backward compatible)
        return p.to_dict()


# ----------------------------- Minimal usage example (optional) -----------------------------
if __name__ == "__main__":
    # Example: build a portfolio with trades
    assistant = PortfolioAIAssistant(
        provider="ollama",
        model="qwen3:14b",
        finance_provider="yfinance",
        ensemble=False,
        user_response_preferences="Explain very detailed"
    )

    pf = assistant.new_portfolio("Sample Portfolio", "Long-term growth / balanced risk")
    pf.add_asset("MBGAF", name="Mercedes-Benz Group")
    pf.add_trade("MBGAF", quantity=10, price=50.10, date_str="2023-05-01")
    pf.add_trade("MBGAF", quantity=56, price=52.00, date_str="2023-06-01")

    pf.add_asset("GOOG", name="Alphabet")
    pf.add_trade("GOOG", quantity=25, price=134.50, date_str="2023-02-15")


    pf.save_to_file("./tmp_data/portfolio_before_evaluation.json")

    # Evaluate (public API unchanged) - accepts dict or Portfolio
    result = assistant.evaluate_portfolio(pf, specific_assets=["MBGAF", "GOOG"])
    print(json.dumps(result, indent=2))

    pf.save_to_file("./tmp_data/portfolio_after_evaluation.json")
