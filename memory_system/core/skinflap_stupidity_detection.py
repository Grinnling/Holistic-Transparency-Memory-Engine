class QueryStupidityDetector:
    """Detects problematic queries and suggests reforms before processing"""
    
    def __init__(self):
        self.stupidity_patterns = {
            'contradiction_tracker': self.detect_contradictions,
            'wrong_problem_solver': self.detect_wrong_problem,
            'premature_optimizer': self.detect_premature_optimization,
            'assumption_validator': self.detect_untested_assumptions,
            'overengineering_detector': self.detect_overengineering,
            'scope_creep_tracker': self.detect_scope_creep,
            'context_whiplash': self.detect_topic_jumping,
            'impossible_request': self.detect_physics_violations,
            'vague_request': self.detect_mind_reading_expectations,
            'missing_info': self.detect_information_gaps,
            'complexity_blindness': self.detect_hidden_complexity,
            # New clarity detectors
            'context_free_pronouns': self.detect_context_free_pronouns,
            'incomplete_requests': self.detect_incomplete_requests,
            'assumed_knowledge': self.detect_assumed_knowledge,
            'location_references': self.detect_location_references
        }
        
    def analyze_query(self, query, conversation_history):
        """Analyze query for problematic patterns before processing"""
        detected_issues = []
        
        for pattern_name, detector in self.stupidity_patterns.items():
            if detector(query, conversation_history):
                detected_issues.append({
                    'pattern': pattern_name,
                    'description': self.generate_intervention(pattern_name),
                    'suggested_reform': self.suggest_query_reform(pattern_name, query)
                })
                
        return QueryAnalysisResult(
            original_query=query,
            issues_detected=detected_issues,
            needs_reformation=len(detected_issues) > 0,
            severity=self.calculate_severity(detected_issues)
        )
    
    def generate_intervention(self, pattern_type):
        """Generate pattern descriptions for detected issues (for model context)"""
        interventions = {
            'contradiction_tracker': "Query contradicts previous statements",
            'wrong_problem_solver': "Request treats symptoms rather than root cause", 
            'premature_optimizer': "Optimization request for non-critical path",
            'assumption_validator': "Contains unvalidated assumptions",
            'overengineering_detector': "Complex solution proposed for simple problem",
            'scope_creep_tracker': "Request has expanded beyond original scope",
            'context_whiplash': "Sudden topic change without context bridge",
            'impossible_request': "Violates engineering constraints (fast + cheap + perfect)",
            'vague_request': "Too vague for specific help",
            'missing_info': "Lacks actionable information",
            'complexity_blindness': "Simple request with complex implications",
            # New clarity detectors
            'context_free_pronouns': "Uses pronouns without clear antecedents",
            'incomplete_requests': "Request seems incomplete or trails off", 
            'assumed_knowledge': "References unstated previous context",
            'location_references': "Vague file/code location references"
        }
        
        return interventions.get(pattern_type, "Unclear request pattern detected")
    
    def suggest_query_reform(self, pattern_type, original_query):
        """Suggest better ways to phrase the query"""
        reform_strategies = {
            'vague_request': f"Instead of '{original_query}', try: 'I want to improve [specific aspect] by [specific method] to achieve [specific outcome]'",
            'missing_info': f"Consider adding: context, constraints, expected outcome, and success criteria to '{original_query}'",
            'scope_creep_tracker': f"Try breaking '{original_query}' into: Phase 1 (core functionality), Phase 2 (enhancements), Phase 3 (nice-to-haves)",
            'impossible_request': f"Prioritize '{original_query}' by choosing: most important aspect, acceptable trade-offs, and minimum viable solution",
            'overengineering_detector': f"Simplify '{original_query}' to: what's the smallest thing that would solve the core problem?"
        }
        
        return reform_strategies.get(pattern_type, f"Consider rephrasing '{original_query}' with more specific details")
    
    def calculate_severity(self, issues):
        """Calculate how problematic the query is"""
        if not issues:
            return 'clean'
        elif len(issues) == 1:
            return 'minor'
        elif len(issues) <= 3:
            return 'moderate'
        else:
            return 'major'
    
    # Detection methods (same as before but focused on query analysis)
    def detect_contradictions(self, query, history):
        """Check if query contradicts recent statements"""
        return self._analyze_contradictory_statements(query, history)
        
    def detect_wrong_problem(self, query, history):
        """Detect when query addresses symptoms vs root cause"""
        symptom_indicators = ['hide', 'suppress', 'remove error', 'make smaller', 'quiet']
        return any(indicator in query.lower() for indicator in symptom_indicators)
        
    def detect_premature_optimization(self, query, history):
        """Detect optimization of non-critical paths"""
        optimization_words = ['optimize', 'faster', 'performance', 'speed up']
        rare_usage_indicators = ['monthly', 'yearly', 'occasionally', 'sometimes']
        
        has_optimization = any(word in query.lower() for word in optimization_words)
        suggests_rare_use = any(indicator in query.lower() for indicator in rare_usage_indicators)
        
        return has_optimization and suggests_rare_use
        
    def detect_untested_assumptions(self, query, history):
        """Check for unvalidated assumptions in query"""
        assumption_keywords = ["obviously", "clearly", "everyone knows", "users want", "people need", "should be simple"]
        return any(keyword in query.lower() for keyword in assumption_keywords)
        
    def detect_overengineering(self, query, history):
        """Detect unnecessarily complex solutions for simple problems"""
        complexity_indicators = ["microservices", "enterprise", "scalable", "framework", "architecture", "distributed"]
        simple_problem_indicators = ["simple", "basic", "quick", "small", "todo", "list", "form"]
        
        has_complexity = any(indicator in query.lower() for indicator in complexity_indicators)
        has_simplicity = any(indicator in query.lower() for indicator in simple_problem_indicators)
        
        return has_complexity and has_simplicity
        
    def detect_scope_creep(self, query, history):
        """Detect when query expands beyond original scope"""
        if not history:
            return False
            
        # Look for expansion keywords in current query vs history
        expansion_indicators = ["also", "and", "plus", "additionally", "while we're at it"]
        feature_additions = ["feature", "functionality", "capability", "option", "setting"]
        
        has_expansion = any(indicator in query.lower() for indicator in expansion_indicators)
        adds_features = any(addition in query.lower() for addition in feature_additions)
        
        return has_expansion and adds_features
        
    def detect_topic_jumping(self, query, history):
        """Detect sudden topic changes without context bridge"""
        if not history or len(history) < 2:
            return False
            
        # Simple topic detection based on key domain words
        last_context = history[-1].lower() if history else ""
        current_query = query.lower()
        
        # Define topic domains
        domains = {
            'tech': ['code', 'programming', 'software', 'database', 'server'],
            'business': ['revenue', 'customers', 'market', 'sales', 'strategy'],
            'design': ['ui', 'ux', 'layout', 'visual', 'interface'],
            'operations': ['deployment', 'monitoring', 'infrastructure', 'scaling']
        }
        
        last_domain = self._detect_domain(last_context, domains)
        current_domain = self._detect_domain(current_query, domains)
        
        return last_domain and current_domain and last_domain != current_domain
        
    def detect_physics_violations(self, query, history):
        """Detect impossible constraint combinations"""
        constraints = {
            'speed': ['fast', 'quick', 'immediate', 'instant', 'asap', 'urgent'],
            'cost': ['cheap', 'free', 'budget', 'low-cost', 'minimal cost'],
            'quality': ['perfect', 'flawless', 'enterprise-grade', 'production-ready', 'robust'],
            'scope': ['everything', 'all features', 'comprehensive', 'complete', 'full-featured']
        }
        
        detected_constraints = 0
        for constraint_type, keywords in constraints.items():
            if any(keyword in query.lower() for keyword in keywords):
                detected_constraints += 1
                
        return detected_constraints >= 3
        
    def detect_mind_reading_expectations(self, query, history):
        """Detect vague queries expecting specific outcomes"""
        vague_indicators = ["better", "fix it", "improve", "optimize", "make it work", "handle this", "deal with"]
        return any(query.lower().strip().startswith(indicator) for indicator in vague_indicators)
        
    def detect_information_gaps(self, query, history):
        """Detect when query lacks actionable information"""
        query_lower = query.lower().strip()
        
        # Conversational patterns that are perfectly fine without specifics
        conversational_patterns = [
            # Greetings
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'howdy', 'greetings', 'sup', 'yo', 'hiya',
            # Social responses  
            'thanks', 'thank you', 'yes', 'no', 'ok', 'okay', 'sure', 'please', 
            'sorry', 'excuse me', 'pardon', 'bye', 'goodbye', 'see you', 'later',
            # Simple questions that don't need specifics
            'how are you', 'what are you', 'who are you', 'can you help', 'help me'
        ]
        
        # If it matches conversational patterns, it's fine
        if any(pattern in query_lower for pattern in conversational_patterns):
            return False
        
        # If it's very short and looks conversational, probably fine
        if len(query.split()) <= 3 and any(char in query for char in '?!'):
            return False
        
        # For longer queries, check for actionable information
        actionable_elements = ['what', 'where', 'when', 'how', 'which', 'who']
        specific_nouns = [word for word in query.split() if len(word) > 4 and word.isalpha()]
        
        has_question_words = any(element in query_lower for element in actionable_elements)
        has_specifics = len(specific_nouns) >= 2
        
        # Only flag as information gap if it's a longer query (5+ words) without actionable info
        return len(query.split()) >= 5 and not (has_question_words or has_specifics)
        
    def detect_hidden_complexity(self, query, history):
        """Detect simple-sounding requests with complex implications"""
        simple_words = ['just', 'simply', 'easily', 'quickly', 'only']
        complex_domains = ['authentication', 'security', 'migration', 'integration', 'scalability', 'real-time']
        
        seems_simple = any(word in query.lower() for word in simple_words)
        is_complex_domain = any(domain in query.lower() for domain in complex_domains)
        
        return seems_simple and is_complex_domain
    
    # New clarity detectors
    def detect_context_free_pronouns(self, query, history):
        """Detect pronouns without clear antecedents"""
        query_lower = query.lower().strip()
        
        # Skip obviously conversational queries
        conversational_patterns = ['how is this', 'what is this', 'how are these', 'what are these']
        if any(pattern in query_lower for pattern in conversational_patterns):
            return False
        
        # Check for pronouns that might lack context
        ambiguous_pronouns = ['this', 'that', 'these', 'those', 'them', 'they']
        
        for pronoun in ambiguous_pronouns:
            if f' {pronoun} ' in f' {query_lower} ' or query_lower.startswith(f'{pronoun} '):
                # Simple check: if no clear noun follows the pronoun, it might be ambiguous
                words = query_lower.split()
                try:
                    pronoun_index = words.index(pronoun)
                    # If pronoun is at end of sentence or followed by verb, it's potentially ambiguous
                    if (pronoun_index == len(words) - 1 or 
                        words[pronoun_index + 1] in ['are', 'is', 'were', 'was', 'will', 'should', 'can']):
                        return True
                except ValueError:
                    continue
        
        return False
    
    def detect_incomplete_requests(self, query, history):
        """Detect incomplete or trailing-off requests"""
        query_lower = query.lower().strip()
        
        # Check for trailing ellipsis
        if query.endswith('...'):
            return True
        
        # Check for incomplete sentence patterns
        incomplete_starters = [
            'can you help with', 'what about', 'should i', 'could we', 
            'maybe we could', 'i was thinking', 'how about'
        ]
        
        for starter in incomplete_starters:
            if query_lower.startswith(starter):
                # If very short after the starter, likely incomplete
                remaining_words = len(query_lower.replace(starter, '').strip().split())
                if remaining_words < 3:
                    return True
        
        return False
    
    def detect_assumed_knowledge(self, query, history):
        """Detect references to unstated previous context"""
        query_lower = query.lower()
        
        assumption_patterns = [
            'like we discussed', 'as mentioned', 'from before', 'the usual way',
            'you know', 'as always', 'like last time', 'the normal approach',
            'as usual', 'like before', 'the standard method'
        ]
        
        return any(pattern in query_lower for pattern in assumption_patterns)
    
    def detect_location_references(self, query, history):
        """Detect vague file/code location references"""
        query_lower = query.lower()
        
        vague_locations = [
            'in that file', 'the function above', 'this code', 'over there',
            'in the other file', 'that class', 'the method', 'this component',
            'that script', 'the config', 'this module', 'that part'
        ]
        
        return any(location in query_lower for location in vague_locations)
    
    # Helper methods
    def _analyze_contradictory_statements(self, query, history):
        """Analyze for contradictions - enhanced implementation"""
        if not history:
            return False
            
        # Look for negation patterns
        current_negations = self._extract_negations(query)
        historical_statements = [self._extract_core_statements(h) for h in history[-3:]]
        
        # Check if current negations contradict historical statements
        for negation in current_negations:
            for statement in historical_statements:
                if self._statements_contradict(negation, statement):
                    return True
        return False
    
    def _detect_domain(self, text, domains):
        """Detect which domain text belongs to"""
        for domain_name, keywords in domains.items():
            if any(keyword in text for keyword in keywords):
                return domain_name
        return None
    
    def _extract_negations(self, text):
        """Extract negative statements from text"""
        negation_patterns = ['not', 'don\'t', 'won\'t', 'can\'t', 'shouldn\'t', 'never']
        # Simple implementation - could be more sophisticated
        return [phrase for phrase in text.split('.') if any(neg in phrase.lower() for neg in negation_patterns)]
    
    def _extract_core_statements(self, text):
        """Extract core positive statements from text"""
        # Simplified implementation
        return [phrase.strip() for phrase in text.split('.') if phrase.strip()]
    
    def _statements_contradict(self, negation, statement):
        """Check if a negation contradicts a statement"""
        # Simplified contradiction detection
        neg_words = set(negation.lower().split())
        stmt_words = set(statement.lower().split())
        return len(neg_words.intersection(stmt_words)) > 2


class QueryAnalysisResult:
    """Result of query stupidity analysis"""
    
    def __init__(self, original_query, issues_detected, needs_reformation, severity):
        self.original_query = original_query
        self.issues_detected = issues_detected
        self.needs_reformation = needs_reformation
        self.severity = severity
    
    def format_clarification_request(self):
        """Format the issues into a clarification request"""
        if not self.needs_reformation:
            return None
            
        if len(self.issues_detected) == 1:
            issue = self.issues_detected[0]
            return f"""
Query has clarity issue: {issue['description']}

Pattern: {issue['pattern']}
Suggested reform: {issue['suggested_reform']}
            """
        else:
            return f"""
Multiple issues detected with query:

{chr(10).join(f"• {issue['pattern']}: {issue['description']}" for issue in self.issues_detected)}

Would you like to:
1. Address these issues one by one
2. Rephrase the entire query
3. Break it into smaller, clearer requests
4. Proceed anyway (I'll do my best with what I understand)
            """


class CollaborativeQueryReformer:
    """Main system for detecting and reforming problematic queries"""
    
    def __init__(self):
        self.detector = QueryStupidityDetector()
        self.reformation_history = []
        self.auto_reform_enabled = True
        
    def process_query(self, query, conversation_history):
        """Main entry point for query processing"""
        
        # Analyze the query for issues
        analysis = self.detector.analyze_query(query, conversation_history)
        
        # Record the analysis
        self.reformation_history.append({
            'original_query': query,
            'analysis': analysis,
            'timestamp': self._get_timestamp()
        })
        
        if not analysis.needs_reformation:
            return QueryReformationResult(
                original_query=query,
                reformed_query=query,
                reformation_applied=False,
                ready_for_processing=True
            )
        
        # Query needs reformation
        clarification = analysis.format_clarification_request()
        
        return QueryReformationResult(
            original_query=query,
            reformed_query=None,
            reformation_applied=False,
            ready_for_processing=False,
            clarification_needed=clarification,
            detected_issues=analysis.issues_detected
        )
    
    def apply_user_reforms(self, original_query, user_responses):
        """Apply user-provided clarifications to reform the query"""
        # This would combine original query with user clarifications
        reformed_query = self._combine_query_and_clarifications(original_query, user_responses)
        
        # Re-analyze the reformed query
        re_analysis = self.detector.analyze_query(reformed_query, [])
        
        return QueryReformationResult(
            original_query=original_query,
            reformed_query=reformed_query,
            reformation_applied=True,
            ready_for_processing=not re_analysis.needs_reformation,
            clarification_needed=re_analysis.format_clarification_request() if re_analysis.needs_reformation else None
        )
    
    def _combine_query_and_clarifications(self, query, clarifications):
        """Combine original query with user clarifications"""
        # Simple implementation - could be more sophisticated
        return f"{query} [Clarified: {'; '.join(clarifications)}]"
    
    def _get_timestamp(self):
        """Get current timestamp"""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def get_reformation_stats(self):
        """Get statistics on query reformations"""
        if not self.reformation_history:
            return "No query reformations recorded yet"
            
        total_queries = len(self.reformation_history)
        problematic_queries = len([r for r in self.reformation_history if r['analysis'].needs_reformation])
        
        return {
            'total_queries_processed': total_queries,
            'problematic_queries': problematic_queries,
            'clean_query_rate': (total_queries - problematic_queries) / total_queries if total_queries > 0 else 0,
            'most_common_issues': self._analyze_common_issues()
        }
    
    def _analyze_common_issues(self):
        """Analyze most common query issues"""
        issue_counts = {}
        for record in self.reformation_history:
            if record['analysis'].needs_reformation:
                for issue in record['analysis'].issues_detected:
                    pattern = issue['pattern']
                    issue_counts[pattern] = issue_counts.get(pattern, 0) + 1
        
        return sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)


class QueryReformationResult:
    """Result of query reformation process"""
    
    def __init__(self, original_query, reformed_query, reformation_applied, ready_for_processing, 
                 clarification_needed=None, detected_issues=None):
        self.original_query = original_query
        self.reformed_query = reformed_query
        self.reformation_applied = reformation_applied
        self.ready_for_processing = ready_for_processing
        self.clarification_needed = clarification_needed
        self.detected_issues = detected_issues or []


# Example integration with RAG pipeline
class EnhancedRAGPipeline:
    """RAG pipeline with query reformation"""
    
    def __init__(self):
        self.query_reformer = CollaborativeQueryReformer()
        # ... other RAG components
    
    def process_user_input(self, user_query, conversation_history):
        """Process user input through reformation then RAG"""
        
        # 1. Query reformation phase
        reformation_result = self.query_reformer.process_query(user_query, conversation_history)
        
        if not reformation_result.ready_for_processing:
            # Return clarification request instead of proceeding
            return {
                'type': 'clarification_needed',
                'message': reformation_result.clarification_needed,
                'original_query': user_query
            }
        
        # 2. Proceed with RAG pipeline using reformed query
        final_query = reformation_result.reformed_query
        
        # Continue with normal RAG processing...
        return self.process_rag_pipeline(final_query, conversation_history)
    
    def process_rag_pipeline(self, query, history):
        """Standard RAG processing (placeholder)"""
        return {
            'type': 'rag_response',
            'query': query,
            'response': f"Processing reformed query: {query}"
        }


# Example usage
if __name__ == "__main__":
    pipeline = EnhancedRAGPipeline()
    
    # Test problematic queries
    test_queries = [
        "Make it better",
        "I want it fast, cheap, and perfect by tomorrow",
        "Just add simple user authentication with OAuth, SAML, and biometrics",
        "Build enterprise microservices for this todo list",
        "Optimize this function that runs once a year"
    ]
    
    conversation_history = []
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"User Query: {query}")
        print(f"{'='*60}")
        
        result = pipeline.process_user_input(query, conversation_history)
        
        if result['type'] == 'clarification_needed':
            print("🔧 QUERY REFORMATION NEEDED:")
            print(result['message'])
        else:
            print("✅ QUERY PROCESSED:")
            print(result['response'])
        
        conversation_history.append(query)