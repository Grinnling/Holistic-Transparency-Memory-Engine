#!/usr/bin/env python3
"""
Smart Retrieval Manager for Working Memory
Provides intelligent search, keyword matching, and relevance scoring
"""

import re
import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Set
from collections import defaultdict, Counter
import json

logger = logging.getLogger(__name__)

class KeywordExtractor:
    """Extracts meaningful keywords from conversation text"""
    
    def __init__(self):
        # Common stop words to filter out
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 'have',
            'had', 'what', 'said', 'each', 'which', 'their', 'time', 'would',
            'there', 'we', 'when', 'where', 'who', 'why', 'how', 'all', 'any',
            'both', 'can', 'could', 'do', 'does', 'either', 'few', 'may',
            'might', 'must', 'neither', 'nor', 'or', 'same', 'should', 'since',
            'some', 'such', 'than', 'too', 'very', 'well', 'were'
        }
        
        # Technical terms that should always be considered important
        self.technical_keywords = {
            'api', 'database', 'server', 'client', 'function', 'class', 'method',
            'variable', 'error', 'bug', 'fix', 'code', 'script', 'config',
            'authentication', 'security', 'token', 'password', 'encryption',
            'docker', 'container', 'service', 'endpoint', 'request', 'response',
            'json', 'http', 'https', 'url', 'debug', 'test', 'production',
            'development', 'deployment', 'backup', 'restore', 'migration',
            'performance', 'optimization', 'memory', 'cpu', 'disk', 'network'
        }
        
        # Pattern for extracting code-like terms
        self.code_pattern = re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b|\b[a-zA-Z_][a-zA-Z0-9_]*\(\)')
        
        # Pattern for file paths and URLs
        self.path_pattern = re.compile(r'[/\\][\w\-./\\]+|https?://[\w\-._~:/?#[\]@!$&\'()*+,;=%]+')
    
    def extract_keywords(self, text: str, min_length: int = 3) -> Dict[str, int]:
        """Extract keywords with their frequencies"""
        if not text:
            return {}
        
        text_lower = text.lower()
        keywords = Counter()
        
        # Extract regular words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text_lower)
        for word in words:
            if (word not in self.stop_words and 
                len(word) >= min_length and 
                not word.isdigit()):
                keywords[word] += 1
        
        # Extract technical terms (even if they're in stop words list)
        for tech_term in self.technical_keywords:
            if tech_term in text_lower:
                count = text_lower.count(tech_term)
                keywords[tech_term] = max(keywords.get(tech_term, 0), count * 2)  # Boost technical terms
        
        # Extract code-like terms
        code_matches = self.code_pattern.findall(text)
        for match in code_matches:
            keywords[match.lower()] += 2  # Code references are important
        
        # Extract file paths and URLs
        path_matches = self.path_pattern.findall(text)
        for match in path_matches:
            # Extract filename or last path component
            path_parts = match.split('/')
            if path_parts:
                filename = path_parts[-1]
                if filename and len(filename) > 2:
                    keywords[filename.lower()] += 2
        
        return dict(keywords)
    
    def extract_context_keywords(self, context_used: List[str]) -> Set[str]:
        """Extract keywords from context metadata"""
        context_keywords = set()
        
        for context_item in context_used or []:
            # Split context names and extract meaningful parts
            parts = re.split(r'[_\-\s]+', context_item.lower())
            for part in parts:
                if len(part) > 2 and part not in self.stop_words:
                    context_keywords.add(part)
        
        return context_keywords

class RelevanceScorer:
    """Calculates relevance scores for memory retrieval"""
    
    def __init__(self):
        self.keyword_extractor = KeywordExtractor()
    
    def calculate_text_similarity(self, query_keywords: Dict[str, int], 
                                 target_keywords: Dict[str, int]) -> float:
        """Calculate text similarity using weighted keyword overlap"""
        if not query_keywords or not target_keywords:
            return 0.0
        
        # Calculate weighted intersection
        common_keywords = set(query_keywords.keys()) & set(target_keywords.keys())
        if not common_keywords:
            return 0.0
        
        # Weight by frequency and importance
        similarity_score = 0.0
        total_query_weight = sum(query_keywords.values())
        
        for keyword in common_keywords:
            query_weight = query_keywords[keyword] / total_query_weight
            target_weight = min(target_keywords[keyword], 5) / 5  # Cap at 5 to prevent spam
            similarity_score += query_weight * target_weight
        
        # Normalize by the number of unique keywords in query
        return similarity_score * len(common_keywords) / len(query_keywords)
    
    def calculate_context_similarity(self, query_context: Set[str], 
                                   target_context: Set[str]) -> float:
        """Calculate context similarity based on overlap"""
        if not query_context or not target_context:
            return 0.0
        
        intersection = query_context & target_context
        union = query_context | target_context
        
        # Jaccard similarity with boost for exact matches
        jaccard = len(intersection) / len(union)
        exact_match_boost = len(intersection) / len(query_context)
        
        return (jaccard + exact_match_boost) / 2
    
    def calculate_temporal_relevance(self, exchange_timestamp: str, 
                                   decay_hours: float = 24.0) -> float:
        """Calculate temporal relevance with exponential decay"""
        try:
            # Handle both timezone-aware and naive timestamps
            if 'T' in exchange_timestamp:
                if '+' in exchange_timestamp or 'Z' in exchange_timestamp:
                    exchange_time = datetime.fromisoformat(exchange_timestamp.replace('Z', '+00:00'))
                else:
                    # Assume UTC for naive timestamps
                    exchange_time = datetime.fromisoformat(exchange_timestamp).replace(tzinfo=timezone.utc)
            else:
                # Fallback for malformed timestamps
                return 0.5
            
            current_time = datetime.now(timezone.utc)
            hours_ago = (current_time - exchange_time).total_seconds() / 3600
            
            # Handle negative time (future timestamps) 
            if hours_ago < 0:
                hours_ago = 0
            
            # Exponential decay: more recent = higher score
            return math.exp(-hours_ago / decay_hours)
            
        except (ValueError, AttributeError, TypeError):
            # If timestamp parsing fails, assume moderate relevance
            return 0.5
    
    def calculate_significance_boost(self, exchange: Dict) -> float:
        """Boost score based on exchange significance"""
        encryption_metadata = exchange.get('encryption_metadata', {})
        significance_analysis = encryption_metadata.get('sensitivity_analysis', {})
        
        # Use significance score if available
        if 'total_significance_score' in significance_analysis:
            score = significance_analysis['total_significance_score']
            # Normalize to 0-1 range with diminishing returns
            return min(1.0, score / 50.0)  # Score of 50 = max boost
        
        # Fallback: look for importance indicators
        text = f"{exchange.get('user_message', '')} {exchange.get('assistant_response', '')}"
        importance_words = ['important', 'critical', 'urgent', 'error', 'bug', 'fix', 'solution']
        
        importance_count = sum(text.lower().count(word) for word in importance_words)
        return min(1.0, importance_count / 5.0)  # Up to 5 importance words = max boost

class SmartRetrieval:
    """Smart retrieval system for working memory"""
    
    def __init__(self):
        self.keyword_extractor = KeywordExtractor()
        self.relevance_scorer = RelevanceScorer()
        
        # Cache for processed exchange metadata
        self.exchange_cache = {}
        
        logger.info("Smart retrieval system initialized")
    
    def _process_exchange(self, exchange: Dict) -> Dict:
        """Process exchange and cache keywords and metadata"""
        exchange_id = exchange.get('exchange_id', 'unknown')
        
        if exchange_id in self.exchange_cache:
            return self.exchange_cache[exchange_id]
        
        # Extract keywords from user message and assistant response
        user_keywords = self.keyword_extractor.extract_keywords(
            exchange.get('user_message', '')
        )
        assistant_keywords = self.keyword_extractor.extract_keywords(
            exchange.get('assistant_response', '')
        )
        
        # Combine keywords with weight adjustment
        combined_keywords = Counter(user_keywords)
        for keyword, count in assistant_keywords.items():
            combined_keywords[keyword] += count * 0.8  # Assistant response slightly less weight
        
        # Extract context keywords
        context_keywords = self.keyword_extractor.extract_context_keywords(
            exchange.get('context_used', [])
        )
        
        # Store processed data
        processed = {
            'exchange_id': exchange_id,
            'keywords': dict(combined_keywords),
            'context_keywords': context_keywords,
            'timestamp': exchange.get('timestamp', datetime.utcnow().isoformat()),
            'word_count': len(exchange.get('user_message', '').split()) + 
                         len(exchange.get('assistant_response', '').split())
        }
        
        self.exchange_cache[exchange_id] = processed
        return processed
    
    def search_exchanges(self, query: str, exchanges: List[Dict], 
                        context_filter: List[str] = None,
                        max_results: int = 10,
                        min_relevance: float = 0.1) -> List[Dict]:
        """Search exchanges with smart relevance ranking"""
        
        if not query.strip():
            return []
        
        # Extract query keywords and context
        query_keywords = self.keyword_extractor.extract_keywords(query)
        query_context = self.keyword_extractor.extract_context_keywords(context_filter or [])
        
        if not query_keywords:
            return []
        
        # Score all exchanges
        scored_exchanges = []
        
        for exchange in exchanges:
            processed = self._process_exchange(exchange)
            
            # Calculate different similarity components
            text_similarity = self.relevance_scorer.calculate_text_similarity(
                query_keywords, processed['keywords']
            )
            
            context_similarity = self.relevance_scorer.calculate_context_similarity(
                query_context, processed['context_keywords']
            )
            
            temporal_relevance = self.relevance_scorer.calculate_temporal_relevance(
                processed['timestamp']
            )
            
            significance_boost = self.relevance_scorer.calculate_significance_boost(exchange)
            
            # Combine scores with weights
            relevance_score = (
                text_similarity * 0.5 +           # Main text similarity
                context_similarity * 0.2 +        # Context match
                temporal_relevance * 0.15 +       # Recency
                significance_boost * 0.15         # Importance
            )
            
            # Apply keyword density bonus for short, focused exchanges
            if processed['word_count'] < 100 and text_similarity > 0.3:
                relevance_score *= 1.2  # Boost concise, relevant exchanges
            
            if relevance_score >= min_relevance:
                scored_exchanges.append({
                    'exchange': exchange,
                    'relevance_score': relevance_score,
                    'text_similarity': text_similarity,
                    'context_similarity': context_similarity,
                    'temporal_relevance': temporal_relevance,
                    'significance_boost': significance_boost,
                    'matched_keywords': list(set(query_keywords.keys()) & 
                                           set(processed['keywords'].keys()))
                })
        
        # Sort by relevance score descending
        scored_exchanges.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Return top results
        return scored_exchanges[:max_results]
    
    def find_similar_exchanges(self, reference_exchange: Dict, 
                             exchanges: List[Dict],
                             max_results: int = 5,
                             min_similarity: float = 0.2) -> List[Dict]:
        """Find exchanges similar to a reference exchange"""
        
        ref_processed = self._process_exchange(reference_exchange)
        similar_exchanges = []
        
        for exchange in exchanges:
            if exchange.get('exchange_id') == ref_processed['exchange_id']:
                continue  # Skip self
            
            processed = self._process_exchange(exchange)
            
            # Calculate similarity based on keywords and context
            text_similarity = self.relevance_scorer.calculate_text_similarity(
                ref_processed['keywords'], processed['keywords']
            )
            
            context_similarity = self.relevance_scorer.calculate_context_similarity(
                ref_processed['context_keywords'], processed['context_keywords']
            )
            
            # Combined similarity
            overall_similarity = text_similarity * 0.7 + context_similarity * 0.3
            
            if overall_similarity >= min_similarity:
                similar_exchanges.append({
                    'exchange': exchange,
                    'similarity_score': overall_similarity,
                    'text_similarity': text_similarity,
                    'context_similarity': context_similarity,
                    'common_keywords': list(set(ref_processed['keywords'].keys()) & 
                                          set(processed['keywords'].keys()))
                })
        
        # Sort by similarity
        similar_exchanges.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_exchanges[:max_results]
    
    def get_keyword_summary(self, exchanges: List[Dict], 
                           top_keywords: int = 20) -> Dict:
        """Get summary of most common keywords across exchanges"""
        
        all_keywords = Counter()
        context_keywords = Counter()
        
        for exchange in exchanges:
            processed = self._process_exchange(exchange)
            
            # Aggregate keywords with frequency weighting
            for keyword, count in processed['keywords'].items():
                all_keywords[keyword] += count
            
            # Aggregate context keywords
            for keyword in processed['context_keywords']:
                context_keywords[keyword] += 1
        
        return {
            'total_exchanges': len(exchanges),
            'top_keywords': dict(all_keywords.most_common(top_keywords)),
            'top_context_keywords': dict(context_keywords.most_common(10)),
            'unique_keywords': len(all_keywords),
            'cache_size': len(self.exchange_cache)
        }
    
    def clear_cache(self):
        """Clear the exchange processing cache"""
        self.exchange_cache.clear()
        logger.info("Retrieval cache cleared")
    
    def get_retrieval_stats(self) -> Dict:
        """Get retrieval system statistics"""
        return {
            'cache_size': len(self.exchange_cache),
            'cached_exchanges': list(self.exchange_cache.keys()),
            'keyword_extractor_config': {
                'stop_words_count': len(self.keyword_extractor.stop_words),
                'technical_keywords_count': len(self.keyword_extractor.technical_keywords)
            }
        }