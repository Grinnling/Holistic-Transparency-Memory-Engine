#!/usr/bin/env python3
"""
ResponseEnhancer - Confidence analysis and response enhancement

OMNI-MODEL Design: Two-layer confidence system
1. Native Confidence (via Model Onboarding) - Primary when available
   - Model config declares what confidence it provides
   - More accurate (actual model probabilities)
   - Configured during model onboarding

2. Heuristic Confidence (Pattern-Based) - Fallback + Cross-check
   - Always available regardless of model
   - Analyzes response language for hedging/uncertainty
   - Catches mismatches (high native + lots of hedging = suspicious)

Why Both: They answer different questions:
- Native = "How confident was the model in generating this?"
- Heuristic = "Does this response SOUND confident/uncertain?"

Mismatch detection catches hallucination risk (low native + sounds certain)

Part of Layer 5 extraction from rich_chat.py.
"""

from typing import Optional, Dict, List, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

if TYPE_CHECKING:
    from error_handler import ErrorHandler


class UncertaintyCategory(Enum):
    """Categories of uncertainty {AI} can detect."""
    REAL_TIME_DATA = "real_time"        # Current weather, stocks, news
    TEMPORAL_OUTDATED = "temporal"       # Training data may be old
    PERSONAL_INFO = "personal"           # User-specific info I can't verify
    EXTERNAL_STATE = "external"          # Depends on external systems
    SPECULATION = "speculation"          # I'm inferring, not certain
    AMBIGUOUS_INPUT = "ambiguous"        # Query was vague


class HedgingLevel(Enum):
    """How much hedging language is present."""
    NONE = "none"
    LOW = "low"           # "possibly", "perhaps"
    MEDIUM = "medium"     # "I think", "probably", "might"
    HIGH = "high"         # "I'm not sure", "I don't know"


@dataclass
class PatternRef:
    """Reference to a tracked pattern with temporal context."""
    pattern_id: str              # e.g., "blind_spot:edge_cases"
    timestamp: datetime          # When this instance was noted
    recurrence_count: int        # How many times this pattern has appeared


@dataclass
class CuratorValidation:
    """
    What the Curator tells {ME} about my response.

    This is the feedback that actually helps - external validation
    rather than mechanical pattern matching.
    """

    # Core validation
    confidence: float                    # Overall curator confidence in response
    is_accurate: Optional[bool] = None   # Factual check if verifiable
    answers_question: bool = True        # Did it address what was asked?

    # Actionable feedback
    completeness_gaps: List[str] = field(default_factory=list)  # "You didn't address X"
    correction: Optional[str] = None     # "Actually, Y is correct"

    # Calibration (helps {ME} learn)
    hedging_appropriate: Optional[bool] = None  # Did my uncertainty match reality?
    calibration_note: Optional[str] = None      # "You were confident but wrong about Z"

    # Context tracking
    contradicts_prior: bool = False      # Inconsistent with earlier statements?
    prior_contradiction: Optional[str] = None  # What I contradicted

    # Pattern references (links to Pattern Tracker)
    pattern_refs: List[PatternRef] = field(default_factory=list)


@dataclass
class ConfidenceAnalysis:
    """
    Structured confidence analysis result.

    All fields Optional to support OMNI-MODEL - use what's available.
    """
    # Heuristic analysis (always available)
    hedging_level: HedgingLevel = HedgingLevel.NONE
    hedging_phrases: List[str] = field(default_factory=list)
    uncertainty_categories: List[UncertaintyCategory] = field(default_factory=list)
    heuristic_confidence: float = 1.0  # Our estimate based on patterns

    # Native model confidence (when model provides it)
    native_confidence: Optional[float] = None
    confidence_source: str = "heuristic"  # "heuristic" | "native" | "curator"

    # Curator validation (usually available)
    curator_confidence: Optional[float] = None

    # Cross-validation
    confidence_mismatch: bool = False  # True if native vs heuristic disagree
    mismatch_warning: Optional[str] = None

    # Final combined confidence
    combined_confidence: float = 1.0

    # What to show user
    suggested_caveats: List[str] = field(default_factory=list)
    should_show_warning: bool = False


class ResponseEnhancer:
    """
    Handles response enhancement and confidence analysis.

    OMNI-MODEL Design:
    - Primary: Native confidence from model (when onboarded/available)
    - Fallback: Heuristic analysis (always works)
    - Cross-check: Detect mismatches between native and heuristic

    Similar architecture to skinflap_stupidity_detection but for OUTPUT.
    """

    # Hedging patterns by severity
    HEDGING_PATTERNS = {
        HedgingLevel.HIGH: [
            "I'm not sure", "I don't know", "I can't verify",
            "I cannot confirm", "I'm uncertain", "I have no way to"
        ],
        HedgingLevel.MEDIUM: [
            "I think", "probably", "likely", "might", "could be",
            "may be", "seems like", "appears to", "I believe"
        ],
        HedgingLevel.LOW: [
            "possibly", "perhaps", "maybe", "potentially"
        ]
    }

    # Domain uncertainty triggers (like skinflap patterns)
    UNCERTAINTY_TRIGGERS = {
        UncertaintyCategory.REAL_TIME_DATA: [
            "current", "today", "now", "latest", "live",
            "stock", "weather", "price", "breaking"
        ],
        UncertaintyCategory.TEMPORAL_OUTDATED: [
            "recent", "last week", "yesterday", "2024", "2025", "2026"
        ],
        UncertaintyCategory.PERSONAL_INFO: [
            "your", "you specifically", "your situation",
            "your account", "your file"
        ],
        UncertaintyCategory.EXTERNAL_STATE: [
            "server status", "is it running", "check if",
            "verify that", "confirm whether"
        ]
    }

    # Vague input patterns (from current add_confidence_markers)
    VAGUE_INPUT_PATTERNS = [
        "make it better", "fix this", "help me", "what should i do"
    ]

    def __init__(
        self,
        model_confidence_config: Optional[Dict[str, Any]] = None,
        error_handler: Optional['ErrorHandler'] = None,
        show_confidence: bool = True
    ):
        """
        Initialize ResponseEnhancer.

        Args:
            model_confidence_config: From model onboarding - what confidence the model provides
                Example: {"has_native_confidence": True, "confidence_key": "logprobs"}
            error_handler: Optional ErrorHandler for error routing
            show_confidence: Whether confidence markers are enabled
        """
        self.model_config = model_confidence_config or {}
        self.error_handler = error_handler
        self.show_confidence = show_confidence

    def analyze_confidence(
        self,
        response: str,
        user_message: str,
        native_confidence: Optional[float] = None,
        curator_validation: Optional[CuratorValidation] = None
    ) -> ConfidenceAnalysis:
        """
        Analyze response confidence using all available sources.

        Args:
            response: The assistant's response to analyze
            user_message: Original user message (for context triggers)
            native_confidence: Model-provided confidence (if available)
            curator_validation: Full curator validation (if available)

        Returns:
            ConfidenceAnalysis with all available confidence data
        """
        analysis = ConfidenceAnalysis()

        # 1. Always do heuristic analysis
        analysis.hedging_level, analysis.hedging_phrases = self._detect_hedging(response)
        analysis.uncertainty_categories = self._detect_uncertainty_categories(user_message)
        analysis.heuristic_confidence = self._calculate_heuristic_confidence(
            analysis.hedging_level,
            analysis.uncertainty_categories
        )

        # 2. Use native confidence if provided
        if native_confidence is not None:
            analysis.native_confidence = native_confidence
            analysis.confidence_source = "native"

        # 3. Use curator confidence if provided
        if curator_validation is not None:
            analysis.curator_confidence = curator_validation.confidence

        # 4. Cross-validate and detect mismatches
        analysis.confidence_mismatch, analysis.mismatch_warning = self._check_confidence_mismatch(
            analysis.native_confidence,
            analysis.heuristic_confidence,
            analysis.hedging_level
        )

        # 5. Calculate combined confidence
        analysis.combined_confidence = self._calculate_combined_confidence(analysis)

        # 6. Generate caveats for user
        analysis.suggested_caveats = self._generate_caveats(analysis, user_message)
        analysis.should_show_warning = (
            analysis.confidence_mismatch or
            analysis.combined_confidence < 0.5 or
            len(analysis.uncertainty_categories) > 0
        )

        return analysis

    def enhance_response(
        self,
        response: str,
        user_message: str,
        native_confidence: Optional[float] = None,
        curator_validation: Optional[CuratorValidation] = None
    ) -> str:
        """
        Main entry point - analyze and enhance response with confidence markers.

        Args:
            response: Raw assistant response
            user_message: Original user message
            native_confidence: Model confidence if available
            curator_validation: Full curator validation if available

        Returns:
            Enhanced response with confidence markers (if enabled)
        """
        if not self.show_confidence:
            return response

        analysis = self.analyze_confidence(
            response, user_message, native_confidence, curator_validation
        )

        if not analysis.should_show_warning and not analysis.suggested_caveats:
            return response

        # Build confidence note
        caveat_text = "\n".join(f"- {c}" for c in analysis.suggested_caveats)
        if caveat_text:
            return f"{response}\n\n🤔 **Confidence Note:**\n{caveat_text}"

        return response

    def _detect_hedging(self, response: str) -> tuple[HedgingLevel, List[str]]:
        """
        Detect hedging language in response.

        Aggregates ALL hedging phrases found but returns the HIGHEST severity level.
        This gives full visibility into hedging while using worst-case for confidence calc.
        """
        response_lower = response.lower()
        all_found_phrases = []
        highest_level = HedgingLevel.NONE

        # Check all levels and collect all phrases
        for level in [HedgingLevel.HIGH, HedgingLevel.MEDIUM, HedgingLevel.LOW]:
            for phrase in self.HEDGING_PATTERNS[level]:
                if phrase.lower() in response_lower:
                    all_found_phrases.append(phrase)
                    # Track highest severity found (HIGH > MEDIUM > LOW > NONE)
                    if highest_level == HedgingLevel.NONE:
                        highest_level = level
                    elif level == HedgingLevel.HIGH:
                        highest_level = HedgingLevel.HIGH
                    elif level == HedgingLevel.MEDIUM and highest_level == HedgingLevel.LOW:
                        highest_level = HedgingLevel.MEDIUM

        return highest_level, all_found_phrases

    def _detect_uncertainty_categories(self, user_message: str) -> List[UncertaintyCategory]:
        """Detect what types of uncertainty apply based on user's query."""
        user_lower = user_message.lower()
        categories = []

        for category, triggers in self.UNCERTAINTY_TRIGGERS.items():
            if any(trigger in user_lower for trigger in triggers):
                categories.append(category)

        # Check for vague input
        if any(pattern in user_lower for pattern in self.VAGUE_INPUT_PATTERNS):
            categories.append(UncertaintyCategory.AMBIGUOUS_INPUT)

        return categories

    def _calculate_heuristic_confidence(
        self,
        hedging_level: HedgingLevel,
        uncertainty_categories: List[UncertaintyCategory]
    ) -> float:
        """Calculate confidence estimate from heuristics."""
        # Start at 1.0 and reduce based on findings
        confidence = 1.0

        # Reduce for hedging
        hedging_penalties = {
            HedgingLevel.NONE: 0.0,
            HedgingLevel.LOW: 0.1,
            HedgingLevel.MEDIUM: 0.25,
            HedgingLevel.HIGH: 0.4
        }
        confidence -= hedging_penalties.get(hedging_level, 0)

        # Reduce for each uncertainty category
        confidence -= len(uncertainty_categories) * 0.1

        return max(0.0, min(1.0, confidence))

    def _check_confidence_mismatch(
        self,
        native: Optional[float],
        heuristic: float,
        hedging_level: HedgingLevel
    ) -> tuple[bool, Optional[str]]:
        """Check if native and heuristic confidence disagree (hallucination risk)."""
        if native is None:
            return False, None

        # High native but lots of hedging = suspicious
        if native > 0.8 and hedging_level in [HedgingLevel.HIGH, HedgingLevel.MEDIUM]:
            return True, "Model confident but response contains hedging language"

        # Low native but sounds certain = hallucination risk
        if native < 0.5 and hedging_level == HedgingLevel.NONE:
            return True, "⚠️ Model uncertain but response sounds confident - verify this"

        # Large disagreement
        if abs(native - heuristic) > 0.4:
            return True, f"Confidence mismatch: model={native:.2f}, heuristic={heuristic:.2f}"

        return False, None

    def _calculate_combined_confidence(self, analysis: ConfidenceAnalysis) -> float:
        """Calculate final combined confidence from all sources."""
        sources = []

        if analysis.native_confidence is not None:
            sources.append(('native', analysis.native_confidence, 0.5))  # 50% weight

        if analysis.curator_confidence is not None:
            sources.append(('curator', analysis.curator_confidence, 0.3))  # 30% weight

        sources.append(('heuristic', analysis.heuristic_confidence, 0.2))  # 20% weight

        # Normalize weights
        total_weight = sum(w for _, _, w in sources)
        weighted_sum = sum(conf * (w / total_weight) for _, conf, w in sources)

        # Penalty for mismatch
        if analysis.confidence_mismatch:
            weighted_sum *= 0.8

        return max(0.0, min(1.0, weighted_sum))

    def _generate_caveats(
        self,
        analysis: ConfidenceAnalysis,
        user_message: str
    ) -> List[str]:
        """Generate user-facing caveats based on analysis."""
        caveats = []

        # Category-specific caveats
        category_messages = {
            UncertaintyCategory.REAL_TIME_DATA: "I don't have access to current/real-time information",
            UncertaintyCategory.TEMPORAL_OUTDATED: "My information might be outdated for recent events",
            UncertaintyCategory.PERSONAL_INFO: "I can't verify information specific to your situation",
            UncertaintyCategory.EXTERNAL_STATE: "I can't check external system states",
            UncertaintyCategory.AMBIGUOUS_INPUT: "This seems like a broad request - I might need more specifics"
        }

        for category in analysis.uncertainty_categories:
            if category in category_messages:
                caveats.append(category_messages[category])

        # Mismatch warning
        if analysis.mismatch_warning:
            caveats.append(analysis.mismatch_warning)

        return caveats

    # Toggle methods
    def set_show_confidence(self, enabled: bool) -> None:
        """Enable/disable confidence markers."""
        self.show_confidence = enabled

    def is_confidence_enabled(self) -> bool:
        """Check if confidence markers are enabled."""
        return self.show_confidence

    def update_model_config(self, config: Dict[str, Any]) -> None:
        """Update model confidence config (e.g., after model switch)."""
        self.model_config = config
