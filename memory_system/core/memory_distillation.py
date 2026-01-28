#!/usr/bin/env python3
"""
Memory Distillation System with Learning Mode
Collaborative context compression with user feedback and pattern learning
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict
from collections import defaultdict
import re

# Conditional import for error handler (avoid circular imports)
if TYPE_CHECKING:
    from error_handler import ErrorHandler

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Confirm, Prompt
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

@dataclass
class DistillationDecision:
    """Track a distillation decision for learning"""
    exchange_id: str
    content: str
    original_decision: str  # "keep", "compress", "remove"
    user_correction: str    # "keep", "compress", "remove", "none"
    rationale: str
    timestamp: str
    content_features: Dict[str, Any]  # keywords, length, type, etc.

class MemoryDistillationEngine:
    """Manages context distillation with learning capabilities"""

    def __init__(self, preferences_file: str = "distillation_preferences.json", error_handler: Optional["ErrorHandler"] = None):
        self.console = Console() if RICH_AVAILABLE else None
        self.preferences_file = preferences_file
        self.error_handler = error_handler
        self.load_preferences()

    def _log_error(self, error: Exception, context: str, operation: str):
        """Route error through error_handler if available, otherwise print"""
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            self.error_handler.handle_error(
                error,
                ErrorCategory.GENERAL,  # Distillation is general processing
                ErrorSeverity.LOW_DEBUG,  # Preference file issues are low severity
                context=context,
                operation=operation
            )
        else:
            print(f"❌ [{operation}] {context}: {error}")
        
    def load_preferences(self):
        """Load user preferences from file"""
        try:
            if os.path.exists(self.preferences_file):
                with open(self.preferences_file, 'r') as f:
                    data = json.load(f)
                    self.user_preferences = data.get('preferences', {})
                    self.correction_history = [
                        DistillationDecision(**d) for d in data.get('corrections', [])
                    ]
            else:
                self.user_preferences = {
                    "always_keep_patterns": [],
                    "usually_discard_patterns": [],
                    "learned_rules": [],
                    "correction_count": 0
                }
                self.correction_history = []
        except Exception as e:
            self._log_error(e, "Loading distillation preferences", "load_preferences")
            self.user_preferences = {"correction_count": 0}
            self.correction_history = []
    
    def save_preferences(self):
        """Save preferences to file"""
        try:
            data = {
                'preferences': self.user_preferences,
                'corrections': [asdict(d) for d in self.correction_history]
            }
            with open(self.preferences_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._log_error(e, "Saving distillation preferences", "save_preferences")
    
    def analyze_content_features(self, exchange: Dict) -> Dict[str, Any]:
        """Extract features from an exchange for learning"""
        user_msg = exchange.get('user', '')
        assistant_msg = exchange.get('assistant', '')
        
        features = {
            'user_length': len(user_msg),
            'assistant_length': len(assistant_msg),
            'has_numbers': bool(re.search(r'\d+', user_msg + assistant_msg)),
            'has_questions': '?' in user_msg,
            'is_generic_response': any(phrase in assistant_msg.lower() for phrase in [
                'i understand', 'let me know', 'anything else', 'how can i help'
            ]),
            'is_factual_answer': any(word in assistant_msg.lower() for word in [
                'according to', 'research shows', 'data indicates', 'statistics'
            ]),
            'has_dates': bool(re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}/\d{1,2})', 
                                      (user_msg + assistant_msg).lower())),
            'has_budget_money': bool(re.search(r'\$\d+|budget|cost|price|expensive|cheap', 
                                             (user_msg + assistant_msg).lower())),
            'is_short_response': len(assistant_msg) < 50
        }
        
        return features
    
    def calculate_initial_score(self, exchange: Dict) -> Tuple[str, str]:
        """Calculate initial keep/compress/remove decision with rationale"""
        features = self.analyze_content_features(exchange)
        user_msg = exchange.get('user', '')
        assistant_msg = exchange.get('assistant', '')
        
        # Apply learned rules first
        for rule in self.user_preferences.get('learned_rules', []):
            if self.matches_pattern(exchange, rule):
                return rule['decision'], f"Learned rule: {rule['description']}"
        
        # High value indicators
        if features['has_numbers'] and features['has_budget_money']:
            return "keep", "Contains specific budget/pricing information"
        
        if features['has_questions'] and features['has_dates']:
            return "keep", "User question with temporal specifics"
        
        if features['is_factual_answer'] and not features['is_generic_response']:
            return "keep", "Substantive factual response"
        
        # Low value indicators  
        if features['is_generic_response'] and features['is_short_response']:
            return "remove", "Generic short response with minimal info"
        
        if len(user_msg) < 10 and user_msg.lower() in ['ok', 'yes', 'no', 'thanks', 'sure']:
            return "compress", "Brief acknowledgment"
        
        # Medium value - compress into summary
        if features['assistant_length'] > 200 and not features['is_factual_answer']:
            return "compress", "Long response that could be summarized"
        
        # Default: keep recent exchanges
        return "keep", "Default: preserving for context"
    
    def matches_pattern(self, exchange: Dict, rule: Dict) -> bool:
        """Check if exchange matches a learned rule pattern"""
        content = exchange.get('user', '') + ' ' + exchange.get('assistant', '')
        
        if rule.get('type') == 'keyword':
            return any(keyword.lower() in content.lower() for keyword in rule.get('keywords', []))
        elif rule.get('type') == 'feature':
            features = self.analyze_content_features(exchange)
            return features.get(rule.get('feature_name')) == rule.get('feature_value')
        
        return False
    
    def show_distillation_audit(self, exchanges_to_analyze: List[Dict], buffer_limit: int = 50):
        """Show the memory distillation audit with rationale"""
        if not self.console:
            print("Rich not available for audit display")
            return exchanges_to_analyze[:buffer_limit]
        
        # Trigger silly skinflap alert
        self.show_skinflap_memory_alert(len(exchanges_to_analyze), buffer_limit)
        
        # Analyze each exchange
        decisions = []
        for i, exchange in enumerate(exchanges_to_analyze):
            decision, rationale = self.calculate_initial_score(exchange)
            decisions.append({
                'index': i,
                'exchange': exchange,
                'decision': decision,
                'rationale': rationale,
                'features': self.analyze_content_features(exchange)
            })
        
        # Group by decision
        keeping = [d for d in decisions if d['decision'] == 'keep']
        compressing = [d for d in decisions if d['decision'] == 'compress']  
        removing = [d for d in decisions if d['decision'] == 'remove']
        
        # Display audit
        self.console.print("\n🧠 [bold]MEMORY DISTILLATION AUDIT[/bold]")
        self.console.print(f"Analyzing {len(exchanges_to_analyze)} exchanges, keeping {buffer_limit}")
        
        # Show keeping
        if keeping:
            keep_table = Table(title="🟢 KEEPING (High Value)", border_style="green")
            keep_table.add_column("Ex", width=4)
            keep_table.add_column("Content", style="white")
            keep_table.add_column("Rationale", style="dim")
            
            for item in keeping[-10:]:  # Show last 10
                content = self._format_exchange_preview(item['exchange'])
                keep_table.add_row(str(item['index']), content, item['rationale'])
            
            self.console.print(Panel(keep_table, border_style="green"))
        
        # Show compressing
        if compressing:
            compress_table = Table(title="🟡 COMPRESSING (Pattern → Summary)", border_style="yellow")
            compress_table.add_column("Ex", width=4)
            compress_table.add_column("Content", style="white")
            compress_table.add_column("Rationale", style="dim")
            
            for item in compressing:
                content = self._format_exchange_preview(item['exchange'])
                compress_table.add_row(str(item['index']), content, item['rationale'])
            
            self.console.print(Panel(compress_table, border_style="yellow"))
        
        # Show removing
        if removing:
            remove_table = Table(title="🔴 REMOVING (Low Value)", border_style="red")
            remove_table.add_column("Ex", width=4)
            remove_table.add_column("Content", style="white")
            remove_table.add_column("Rationale", style="dim")
            
            for item in removing:
                content = self._format_exchange_preview(item['exchange'])
                remove_table.add_row(str(item['index']), content, item['rationale'])
                
            self.console.print(Panel(remove_table, border_style="red"))
        
        # Show decision rationale
        rationale_text = Text()
        rationale_text.append("My Decision Logic: ", style="bold")
        rationale_text.append("Prioritized ")
        rationale_text.append("concrete facts", style="green")
        rationale_text.append(" > ")
        rationale_text.append("your questions", style="blue")
        rationale_text.append(" > ")
        rationale_text.append("my substantive answers", style="cyan")
        rationale_text.append(" > ")
        rationale_text.append("social/filler content", style="red")
        
        self.console.print(Panel(rationale_text, title="🤖 My Reasoning"))
        
        # Ask for feedback
        if Confirm.ask("\nDoes this distillation look reasonable?"):
            # Process decisions and return filtered exchanges
            return self._apply_distillation_decisions(decisions, buffer_limit)
        else:
            return self._handle_user_corrections(decisions, buffer_limit)
    
    def _format_exchange_preview(self, exchange: Dict, max_len: int = 60) -> str:
        """Format exchange for display"""
        user = exchange.get('user', '')[:30]
        assistant = exchange.get('assistant', '')[:30]
        
        if len(user) > 27:
            user = user[:27] + "..."
        if len(assistant) > 27:
            assistant = assistant[:27] + "..."
            
        return f"You: {user} | AI: {assistant}"
    
    def _apply_distillation_decisions(self, decisions: List[Dict], buffer_limit: int) -> List[Dict]:
        """Apply distillation decisions and return processed exchanges"""
        result = []
        
        # Keep high-priority exchanges
        keeping = [d for d in decisions if d['decision'] == 'keep']
        for item in keeping[-buffer_limit:]:
            result.append(item['exchange'])
        
        # Add compressed summaries for compressed exchanges
        compressing = [d for d in decisions if d['decision'] == 'compress']
        if compressing:
            summary_content = self._create_compression_summary(compressing)
            result.insert(0, {
                'user': 'SYSTEM_SUMMARY',
                'assistant': summary_content,
                'compressed': True,
                'original_count': len(compressing)
            })
        
        return result
    
    def _create_compression_summary(self, compress_items: List[Dict]) -> str:
        """Create a summary from compressed exchanges"""
        topics = []
        for item in compress_items:
            user_msg = item['exchange'].get('user', '')
            if len(user_msg) > 10:
                topics.append(user_msg[:50])
        
        return f"Previously discussed: {', '.join(topics[:5])}... ({len(compress_items)} exchanges compressed)"
    
    def _handle_user_corrections(self, decisions: List[Dict], buffer_limit: int) -> List[Dict]:
        """Handle user corrections and learn from them"""
        self.console.print("\n[yellow]Let's fix the distillation together![/yellow]")
        
        corrections_made = 0
        for decision in decisions:
            if decision['decision'] in ['remove', 'compress']:
                content_preview = self._format_exchange_preview(decision['exchange'])
                
                new_decision = Prompt.ask(
                    f"\nExchange {decision['index']}: {content_preview}\n"
                    f"My decision: [red]{decision['decision']}[/red] - {decision['rationale']}\n"
                    f"Your preference?",
                    choices=['keep', 'compress', 'remove', 'skip'],
                    default='skip'
                )
                
                if new_decision != 'skip' and new_decision != decision['decision']:
                    # Record the correction
                    correction = DistillationDecision(
                        exchange_id=str(decision['index']),
                        content=content_preview,
                        original_decision=decision['decision'],
                        user_correction=new_decision,
                        rationale=decision['rationale'],
                        timestamp=datetime.now().isoformat(),
                        content_features=decision['features']
                    )
                    
                    self.correction_history.append(correction)
                    decision['decision'] = new_decision  # Update for this session
                    corrections_made += 1
        
        if corrections_made > 0:
            self.user_preferences['correction_count'] += corrections_made
            self.save_preferences()
            self.console.print(f"\n✅ Learned from {corrections_made} corrections!")
            
            # Check if we should suggest rules
            self._suggest_learned_rules()
        
        return self._apply_distillation_decisions(decisions, buffer_limit)
    
    def _suggest_learned_rules(self):
        """Suggest learned rules based on correction patterns"""
        if len(self.correction_history) < 5:
            return
        
        # Analyze patterns
        pattern_analysis = self._analyze_correction_patterns()
        
        for pattern, confidence in pattern_analysis.items():
            if confidence > 0.7:  # 70% confidence threshold
                if Confirm.ask(f"\n💡 LEARNING DETECTED: {pattern}. Should I remember this rule?"):
                    rule = self._create_rule_from_pattern(pattern)
                    self.user_preferences['learned_rules'].append(rule)
                    self.save_preferences()
                    self.console.print(f"✅ Added rule: {rule['description']}")
    
    def _analyze_correction_patterns(self) -> Dict[str, float]:
        """Analyze correction history for patterns"""
        patterns = {}
        
        # Pattern: Always keep exchanges with numbers
        number_corrections = [c for c in self.correction_history if c.content_features.get('has_numbers')]
        if number_corrections:
            keep_ratio = sum(1 for c in number_corrections if c.user_correction == 'keep') / len(number_corrections)
            if keep_ratio > 0.7:
                patterns["You tend to keep exchanges with specific numbers/data"] = keep_ratio
        
        # Pattern: Discard generic responses  
        generic_corrections = [c for c in self.correction_history if c.content_features.get('is_generic_response')]
        if generic_corrections:
            remove_ratio = sum(1 for c in generic_corrections if c.user_correction == 'remove') / len(generic_corrections)
            if remove_ratio > 0.7:
                patterns["You tend to discard generic AI responses"] = remove_ratio
        
        return patterns
    
    def _create_rule_from_pattern(self, pattern: str) -> Dict:
        """Create a rule from an identified pattern"""
        if "numbers" in pattern.lower():
            return {
                'type': 'feature',
                'feature_name': 'has_numbers',
                'feature_value': True,
                'decision': 'keep',
                'description': 'Auto-keep exchanges with numbers/data',
                'created': datetime.now().isoformat()
            }
        elif "generic" in pattern.lower():
            return {
                'type': 'feature', 
                'feature_name': 'is_generic_response',
                'feature_value': True,
                'decision': 'remove',
                'description': 'Auto-remove generic responses',
                'created': datetime.now().isoformat()
            }
        
        return {'description': pattern, 'created': datetime.now().isoformat()}
    
    def show_skinflap_memory_alert(self, current_count: int, limit: int):
        """Show silly skinflap memory pressure alert"""
        pressure = current_count / limit
        
        if pressure > 1.2:
            message = "Blimey! My brain's fuller than a hoarder's attic! Time to Marie Kondo this conversation!"
        elif pressure > 1.0:
            message = "Oy! Memory pressure at maximum chonk! Gotta start chucking some conversational fluff!"
        elif pressure > 0.8:
            message = "Right then, memory's getting thicc! Should I start pruning the chat foliage?"
        else:
            return  # No alert needed
        
        if self.console:
            alert = Panel(
                f"🧠💭 [bold red]SKINFLAP MEMORY ALERT[/bold red]\n\n"
                f"{message}\n\n"
                f"Current: {current_count} exchanges | Limit: {limit}\n"
                f"Pressure: {pressure:.1%}",
                title="🚨 Memory Pressure Warning",
                border_style="red"
            )
            self.console.print(alert)
        else:
            print(f"MEMORY ALERT: {message}")
    
    def show_learning_progress(self):
        """Display learning progress and learned rules"""
        if not self.console:
            return
        
        stats_table = Table(title="📊 Learning Progress")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Total Corrections", str(self.user_preferences.get('correction_count', 0)))
        stats_table.add_row("Learned Rules", str(len(self.user_preferences.get('learned_rules', []))))
        stats_table.add_row("Training Sessions", str(len(set(c.timestamp[:10] for c in self.correction_history))))
        
        self.console.print(Panel(stats_table, title="🤖 My Memory Learning", border_style="blue"))
        
        # Show learned rules
        rules = self.user_preferences.get('learned_rules', [])
        if rules:
            rules_table = Table(title="🧠 Learned Rules")
            rules_table.add_column("Rule", style="white")
            rules_table.add_column("Created", style="dim")
            
            for rule in rules:
                rules_table.add_row(rule.get('description', 'Unknown rule'), rule.get('created', 'Unknown')[:10])
            
            self.console.print(Panel(rules_table, border_style="green"))


# Example usage
if __name__ == "__main__":
    engine = MemoryDistillationEngine()
    
    # Mock conversation data
    mock_exchanges = [
        {"user": "What's the weather like?", "assistant": "I don't have current weather data."},
        {"user": "Budget is $2000 max", "assistant": "Got it, I'll keep the budget at $2000 maximum."},
        {"user": "ok", "assistant": "Great! Let me know if you need anything else."},
        {"user": "What about October weather in Ireland?", "assistant": "October in Ireland averages 60°F with frequent rain."},
        {"user": "thanks", "assistant": "You're welcome! Anything else I can help with?"}
    ]
    
    # Test distillation
    result = engine.show_distillation_audit(mock_exchanges, buffer_limit=3)
    print(f"\nFiltered to {len(result)} exchanges")