#!/usr/bin/env python3
"""
Tests for ResponseEnhancer - Layer 5 extraction from rich_chat.py

Tests cover:
- Heuristic confidence analysis (hedging detection, uncertainty categories)
- Native confidence integration
- Cross-validation and mismatch detection
- Combined confidence calculation
- Response enhancement with caveats
- Toggle functionality
"""

import pytest
from unittest.mock import Mock

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from response_enhancer import (
    ResponseEnhancer,
    ConfidenceAnalysis,
    CuratorValidation,
    HedgingLevel,
    UncertaintyCategory,
    PatternRef
)


class TestHedgingDetection:
    """Tests for hedging language detection."""

    def test_detect_hedging_high(self):
        """Detects high hedging phrases."""
        enhancer = ResponseEnhancer()

        level, phrases = enhancer._detect_hedging(
            "I'm not sure about this, and I can't verify the details."
        )

        assert level == HedgingLevel.HIGH
        assert "I'm not sure" in phrases

    def test_detect_hedging_medium(self):
        """Detects medium hedging phrases."""
        enhancer = ResponseEnhancer()

        level, phrases = enhancer._detect_hedging(
            "I think this might work, but it could be different."
        )

        assert level == HedgingLevel.MEDIUM
        assert any(p in phrases for p in ["I think", "might", "could be"])

    def test_detect_hedging_low(self):
        """Detects low hedging phrases."""
        enhancer = ResponseEnhancer()

        level, phrases = enhancer._detect_hedging(
            "This is possibly the correct approach, perhaps worth trying."
        )

        assert level == HedgingLevel.LOW
        assert any(p in phrases for p in ["possibly", "perhaps"])

    def test_detect_hedging_none(self):
        """No hedging detected in confident response."""
        enhancer = ResponseEnhancer()

        level, phrases = enhancer._detect_hedging(
            "The answer is 42. Python is a programming language."
        )

        assert level == HedgingLevel.NONE
        assert phrases == []


class TestUncertaintyCategories:
    """Tests for uncertainty category detection."""

    def test_detect_real_time_data(self):
        """Detects queries about current/real-time data."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What is the current stock price of AAPL?"
        )

        assert UncertaintyCategory.REAL_TIME_DATA in categories

    def test_detect_temporal_outdated(self):
        """Detects queries about recent events."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What happened last week in the news?"
        )

        assert UncertaintyCategory.TEMPORAL_OUTDATED in categories

    def test_detect_personal_info(self):
        """Detects queries about personal/user-specific info."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What's in your account settings?"
        )

        assert UncertaintyCategory.PERSONAL_INFO in categories

    def test_detect_external_state(self):
        """Detects queries about external system states."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "Check if the server status is running"
        )

        assert UncertaintyCategory.EXTERNAL_STATE in categories

    def test_detect_ambiguous_input(self):
        """Detects vague/ambiguous queries."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "Make it better please"
        )

        assert UncertaintyCategory.AMBIGUOUS_INPUT in categories

    def test_detect_multiple_categories(self):
        """Multiple uncertainty categories can be detected."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What's your current stock portfolio value?"
        )

        # Both real-time (current, stock) and personal (your)
        assert len(categories) >= 2


class TestHeuristicConfidence:
    """Tests for heuristic confidence calculation."""

    def test_full_confidence_no_issues(self):
        """Full confidence when no hedging or uncertainty."""
        enhancer = ResponseEnhancer()

        confidence = enhancer._calculate_heuristic_confidence(
            HedgingLevel.NONE,
            []
        )

        assert confidence == 1.0

    def test_reduced_confidence_with_hedging(self):
        """Confidence reduced by hedging level."""
        enhancer = ResponseEnhancer()

        high_conf = enhancer._calculate_heuristic_confidence(HedgingLevel.HIGH, [])
        medium_conf = enhancer._calculate_heuristic_confidence(HedgingLevel.MEDIUM, [])
        low_conf = enhancer._calculate_heuristic_confidence(HedgingLevel.LOW, [])

        assert high_conf < medium_conf < low_conf < 1.0

    def test_reduced_confidence_with_uncertainty(self):
        """Confidence reduced by uncertainty categories."""
        enhancer = ResponseEnhancer()

        conf_1 = enhancer._calculate_heuristic_confidence(
            HedgingLevel.NONE,
            [UncertaintyCategory.REAL_TIME_DATA]
        )
        conf_2 = enhancer._calculate_heuristic_confidence(
            HedgingLevel.NONE,
            [UncertaintyCategory.REAL_TIME_DATA, UncertaintyCategory.PERSONAL_INFO]
        )

        assert conf_1 < 1.0
        assert conf_2 < conf_1

    def test_confidence_floor_at_zero(self):
        """Confidence never goes below 0."""
        enhancer = ResponseEnhancer()

        # Many uncertainty categories should bottom out at 0
        # HIGH hedging = -0.4, each category = -0.1
        # Need enough to go below 0: 1.0 - 0.4 - (n * 0.1) < 0 => n > 6
        many_categories = [
            UncertaintyCategory.REAL_TIME_DATA,
            UncertaintyCategory.TEMPORAL_OUTDATED,
            UncertaintyCategory.PERSONAL_INFO,
            UncertaintyCategory.EXTERNAL_STATE,
            UncertaintyCategory.AMBIGUOUS_INPUT,
            UncertaintyCategory.SPECULATION,
            UncertaintyCategory.SPECULATION,  # Duplicates still count for calculation
        ]

        confidence = enhancer._calculate_heuristic_confidence(
            HedgingLevel.HIGH,
            many_categories
        )

        assert confidence == 0.0


class TestNativeConfidence:
    """Tests for native confidence integration."""

    def test_native_confidence_used_when_available(self):
        """Native confidence is recorded when provided."""
        enhancer = ResponseEnhancer()

        analysis = enhancer.analyze_confidence(
            response="The answer is 42.",
            user_message="What is the meaning of life?",
            native_confidence=0.95
        )

        assert analysis.native_confidence == 0.95
        assert analysis.confidence_source == "native"

    def test_fallback_to_heuristic_when_no_native(self):
        """Heuristic used when native not available."""
        enhancer = ResponseEnhancer()

        analysis = enhancer.analyze_confidence(
            response="The answer is 42.",
            user_message="What is the meaning of life?",
            native_confidence=None
        )

        assert analysis.native_confidence is None
        assert analysis.confidence_source == "heuristic"


class TestMismatchDetection:
    """Tests for confidence mismatch detection (hallucination risk)."""

    def test_mismatch_high_native_high_hedging(self):
        """Detects mismatch: model confident but response hedges."""
        enhancer = ResponseEnhancer()

        mismatch, warning = enhancer._check_confidence_mismatch(
            native=0.95,
            heuristic=0.6,
            hedging_level=HedgingLevel.HIGH
        )

        assert mismatch is True
        assert "hedging" in warning.lower()

    def test_mismatch_low_native_no_hedging(self):
        """Detects hallucination risk: model uncertain but sounds confident."""
        enhancer = ResponseEnhancer()

        mismatch, warning = enhancer._check_confidence_mismatch(
            native=0.3,
            heuristic=1.0,
            hedging_level=HedgingLevel.NONE
        )

        assert mismatch is True
        assert "verify" in warning.lower()

    def test_no_mismatch_when_aligned(self):
        """No mismatch when native and heuristic agree."""
        enhancer = ResponseEnhancer()

        mismatch, warning = enhancer._check_confidence_mismatch(
            native=0.8,
            heuristic=0.85,
            hedging_level=HedgingLevel.NONE
        )

        assert mismatch is False
        assert warning is None

    def test_no_mismatch_without_native(self):
        """No mismatch check without native confidence."""
        enhancer = ResponseEnhancer()

        mismatch, warning = enhancer._check_confidence_mismatch(
            native=None,
            heuristic=0.5,
            hedging_level=HedgingLevel.HIGH
        )

        assert mismatch is False
        assert warning is None


class TestCombinedConfidence:
    """Tests for combined confidence calculation."""

    def test_combined_confidence_all_sources(self):
        """Combined confidence uses all available sources."""
        enhancer = ResponseEnhancer()

        analysis = ConfidenceAnalysis()
        analysis.native_confidence = 0.8
        analysis.curator_confidence = 0.9
        analysis.heuristic_confidence = 0.7
        analysis.confidence_mismatch = False

        combined = enhancer._calculate_combined_confidence(analysis)

        # Should be weighted average, biased toward native and curator
        assert 0.7 < combined < 0.9

    def test_combined_confidence_heuristic_only(self):
        """Combined confidence falls back to heuristic alone."""
        enhancer = ResponseEnhancer()

        analysis = ConfidenceAnalysis()
        analysis.native_confidence = None
        analysis.curator_confidence = None
        analysis.heuristic_confidence = 0.6
        analysis.confidence_mismatch = False

        combined = enhancer._calculate_combined_confidence(analysis)

        assert combined == 0.6

    def test_mismatch_penalty_applied(self):
        """Mismatch applies penalty to combined confidence."""
        enhancer = ResponseEnhancer()

        analysis_no_mismatch = ConfidenceAnalysis()
        analysis_no_mismatch.native_confidence = 0.8
        analysis_no_mismatch.heuristic_confidence = 0.8
        analysis_no_mismatch.confidence_mismatch = False

        analysis_with_mismatch = ConfidenceAnalysis()
        analysis_with_mismatch.native_confidence = 0.8
        analysis_with_mismatch.heuristic_confidence = 0.8
        analysis_with_mismatch.confidence_mismatch = True

        conf_no_mismatch = enhancer._calculate_combined_confidence(analysis_no_mismatch)
        conf_with_mismatch = enhancer._calculate_combined_confidence(analysis_with_mismatch)

        assert conf_with_mismatch < conf_no_mismatch


class TestResponseEnhancement:
    """Tests for the main enhance_response method."""

    def test_enhance_response_adds_caveats(self):
        """Caveats are added when uncertainty detected."""
        enhancer = ResponseEnhancer(show_confidence=True)

        enhanced = enhancer.enhance_response(
            response="The current price is $150.",
            user_message="What is the current stock price?"
        )

        assert "Confidence Note" in enhanced
        assert "real-time" in enhanced.lower()

    def test_enhance_response_disabled(self):
        """No enhancement when show_confidence is False."""
        enhancer = ResponseEnhancer(show_confidence=False)

        original = "The answer is 42."
        enhanced = enhancer.enhance_response(
            response=original,
            user_message="What is the meaning of life?"
        )

        assert enhanced == original

    def test_enhance_response_no_issues(self):
        """No enhancement when no issues detected."""
        enhancer = ResponseEnhancer(show_confidence=True)

        original = "Python is a programming language."
        enhanced = enhancer.enhance_response(
            response=original,
            user_message="What is Python?"
        )

        # No uncertainty triggers, no hedging - should return original
        assert enhanced == original


class TestCuratorValidation:
    """Tests for CuratorValidation integration."""

    def test_curator_validation_confidence_used(self):
        """Curator confidence is used when validation provided."""
        enhancer = ResponseEnhancer()

        curator_val = CuratorValidation(
            confidence=0.85,
            answers_question=True
        )

        analysis = enhancer.analyze_confidence(
            response="The answer is 42.",
            user_message="What is the meaning?",
            curator_validation=curator_val
        )

        assert analysis.curator_confidence == 0.85

    def test_full_curator_validation_fields(self):
        """CuratorValidation dataclass has all expected fields."""
        validation = CuratorValidation(
            confidence=0.9,
            is_accurate=True,
            answers_question=True,
            completeness_gaps=["missing edge case"],
            correction=None,
            hedging_appropriate=True,
            calibration_note="Good calibration",
            contradicts_prior=False,
            pattern_refs=[]
        )

        assert validation.confidence == 0.9
        assert validation.completeness_gaps == ["missing edge case"]


class TestToggleFunctionality:
    """Tests for toggle methods."""

    def test_toggle_confidence(self):
        """set_show_confidence toggles the setting."""
        enhancer = ResponseEnhancer(show_confidence=True)

        assert enhancer.is_confidence_enabled() is True

        enhancer.set_show_confidence(False)
        assert enhancer.is_confidence_enabled() is False

        enhancer.set_show_confidence(True)
        assert enhancer.is_confidence_enabled() is True

    def test_update_model_config(self):
        """update_model_config replaces the config."""
        enhancer = ResponseEnhancer()

        assert enhancer.model_config == {}

        new_config = {"has_native_confidence": True, "confidence_key": "logprobs"}
        enhancer.update_model_config(new_config)

        assert enhancer.model_config == new_config


class TestVagueInputPatterns:
    """Tests for vague input pattern detection."""

    def test_make_it_better(self):
        """'make it better' detected as ambiguous."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories("make it better")

        assert UncertaintyCategory.AMBIGUOUS_INPUT in categories

    def test_fix_this(self):
        """'fix this' detected as ambiguous."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories("fix this please")

        assert UncertaintyCategory.AMBIGUOUS_INPUT in categories

    def test_help_me(self):
        """'help me' detected as ambiguous."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories("help me with this")

        assert UncertaintyCategory.AMBIGUOUS_INPUT in categories


class TestRealTimeDataTriggers:
    """Tests for real-time data uncertainty triggers."""

    def test_weather_trigger(self):
        """Weather queries trigger uncertainty."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What's the weather like today?"
        )

        assert UncertaintyCategory.REAL_TIME_DATA in categories

    def test_stock_trigger(self):
        """Stock queries trigger uncertainty."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What's the stock price of Tesla?"
        )

        assert UncertaintyCategory.REAL_TIME_DATA in categories

    def test_latest_trigger(self):
        """'latest' queries trigger uncertainty."""
        enhancer = ResponseEnhancer()

        categories = enhancer._detect_uncertainty_categories(
            "What's the latest news?"
        )

        assert UncertaintyCategory.REAL_TIME_DATA in categories


class TestPatternRef:
    """Tests for PatternRef dataclass."""

    def test_pattern_ref_creation(self):
        """PatternRef can be created with all fields."""
        from datetime import datetime

        ref = PatternRef(
            pattern_id="blind_spot:edge_cases",
            timestamp=datetime.now(),
            recurrence_count=3
        )

        assert ref.pattern_id == "blind_spot:edge_cases"
        assert ref.recurrence_count == 3


class TestConfidenceAnalysisDataclass:
    """Tests for ConfidenceAnalysis dataclass."""

    def test_default_values(self):
        """ConfidenceAnalysis has sensible defaults."""
        analysis = ConfidenceAnalysis()

        assert analysis.hedging_level == HedgingLevel.NONE
        assert analysis.hedging_phrases == []
        assert analysis.uncertainty_categories == []
        assert analysis.heuristic_confidence == 1.0
        assert analysis.native_confidence is None
        assert analysis.confidence_source == "heuristic"
        assert analysis.confidence_mismatch is False
        assert analysis.should_show_warning is False


class TestErrorHandling:
    """Tests for error handling - errors route through ErrorHandler."""

    def test_error_handler_receives_errors(self):
        """Errors are routed through ErrorHandler when provided."""
        mock_handler = Mock()
        enhancer = ResponseEnhancer(error_handler=mock_handler)

        # ResponseEnhancer doesn't currently have error-prone operations
        # that would trigger the handler in normal use, but we verify
        # the handler is stored and available
        assert enhancer.error_handler is mock_handler

    def test_works_without_error_handler(self):
        """ResponseEnhancer works fine without an error_handler."""
        enhancer = ResponseEnhancer(error_handler=None)

        # Should not raise
        analysis = enhancer.analyze_confidence(
            response="I think this might work.",
            user_message="Will this work?"
        )

        assert analysis is not None
        assert analysis.hedging_level == HedgingLevel.MEDIUM


class TestHedgingAggregation:
    """Tests for hedging phrase aggregation behavior."""

    def test_aggregates_all_phrases_returns_highest_severity(self):
        """Collects ALL hedging phrases but returns highest severity level."""
        enhancer = ResponseEnhancer()

        # Response with HIGH, MEDIUM, and LOW hedging
        response = (
            "I'm not sure about this. "  # HIGH
            "I think it might work, "     # MEDIUM (I think, might)
            "and it's possibly correct."  # LOW (possibly)
        )

        level, phrases = enhancer._detect_hedging(response)

        # Should return HIGH (highest severity)
        assert level == HedgingLevel.HIGH

        # Should collect ALL phrases found
        assert "I'm not sure" in phrases
        assert any(p in phrases for p in ["I think", "might"])
        assert "possibly" in phrases
        assert len(phrases) >= 4  # At least 4 phrases

    def test_aggregates_medium_and_low(self):
        """Aggregates MEDIUM and LOW phrases, returns MEDIUM."""
        enhancer = ResponseEnhancer()

        response = "I think this could be right, and it's possibly helpful."

        level, phrases = enhancer._detect_hedging(response)

        assert level == HedgingLevel.MEDIUM
        assert any(p in phrases for p in ["I think", "could be"])
        assert "possibly" in phrases

    def test_single_level_still_works(self):
        """Single-level hedging still works correctly."""
        enhancer = ResponseEnhancer()

        response = "I'm not sure and I can't verify this."

        level, phrases = enhancer._detect_hedging(response)

        assert level == HedgingLevel.HIGH
        assert "I'm not sure" in phrases
        assert "I can't verify" in phrases


class TestIntegration:
    """Integration tests - full flow through analyze_confidence."""

    def test_full_analysis_with_all_sources(self):
        """Full analysis path with native, curator, and heuristic confidence."""
        enhancer = ResponseEnhancer(show_confidence=True)

        curator_val = CuratorValidation(
            confidence=0.85,
            is_accurate=True,
            answers_question=True,
            completeness_gaps=[],
            hedging_appropriate=True
        )

        analysis = enhancer.analyze_confidence(
            response="I think the answer might be 42, but I'm not entirely certain.",
            user_message="What is the meaning of life?",
            native_confidence=0.75,
            curator_validation=curator_val
        )

        # All sources should be populated
        assert analysis.native_confidence == 0.75
        assert analysis.curator_confidence == 0.85
        assert analysis.heuristic_confidence < 1.0  # Hedging detected

        # Hedging should be detected
        assert analysis.hedging_level in [HedgingLevel.MEDIUM, HedgingLevel.HIGH]
        assert len(analysis.hedging_phrases) > 0

        # Combined confidence should blend all sources
        assert 0.0 < analysis.combined_confidence < 1.0

        # Source should be native (primary when available)
        assert analysis.confidence_source == "native"

    def test_full_enhancement_flow(self):
        """Full enhance_response flow produces expected output."""
        enhancer = ResponseEnhancer(show_confidence=True)

        enhanced = enhancer.enhance_response(
            response="The weather today is sunny.",
            user_message="What's the current weather?",
            native_confidence=0.6,
            curator_validation=CuratorValidation(confidence=0.7, answers_question=True)
        )

        # Should have confidence note due to real-time data trigger
        assert "Confidence Note" in enhanced
        assert "real-time" in enhanced.lower()

    def test_degraded_mode_heuristic_only(self):
        """Works in degraded mode with only heuristic analysis."""
        enhancer = ResponseEnhancer(show_confidence=True)

        # No native confidence, no curator - heuristic only
        analysis = enhancer.analyze_confidence(
            response="I'm uncertain about this answer.",
            user_message="Is this correct?",
            native_confidence=None,
            curator_validation=None
        )

        assert analysis.native_confidence is None
        assert analysis.curator_confidence is None
        assert analysis.confidence_source == "heuristic"
        assert analysis.heuristic_confidence < 1.0  # Hedging detected
        assert analysis.combined_confidence == analysis.heuristic_confidence

    def test_mismatch_detection_in_full_flow(self):
        """Mismatch detection works in full analysis flow."""
        enhancer = ResponseEnhancer()

        # High native confidence but lots of hedging = suspicious
        analysis = enhancer.analyze_confidence(
            response="I'm not sure, I don't know, I can't verify any of this.",
            user_message="Is the sky blue?",
            native_confidence=0.95  # Very confident model
        )

        assert analysis.confidence_mismatch is True
        assert analysis.mismatch_warning is not None
        assert "hedging" in analysis.mismatch_warning.lower()

        # Combined confidence should be penalized
        assert analysis.combined_confidence < 0.95
