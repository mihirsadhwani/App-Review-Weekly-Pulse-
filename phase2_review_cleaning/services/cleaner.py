import json
import os
import re

class ReviewCleaner:
    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path
        self.output_path = output_path
        
        # Keywords that signify generic praise or vague feedback
        self.low_signal_keywords = {
            'good', 'nice', 'fine', 'ok', 'okay', 'awesome', 'great', 'best', 'excellent',
            'superb', 'amazing', 'wonderful', 'fantastic', 'perfect', 'love', 'liked',
            'app', 'application', 'interface', 'ui', 'experience', 'developer', 'team',
            'work', 'working', 'update', 'software', 'features', 'user', 'service',
            'very', 'so', 'too', 'really', 'much', 'more', 'also', 'and', 'the',
            'secure', 'advance', 'security'
        }
        
        # Keywords that usually indicate specific feedback, issues, or domain-specific mentions
        self.high_signal_keywords = {
            'withdrawal', 'deposit', 'money', 'paisa', 'amount', 'wallet', 'bank', 'account',
            'sip', 'mutual', 'fund', 'stock', 'share', 'order', 'buy', 'sell', 'execution',
            'portfolio', 'profit', 'loss', 'tax', 'charges', 'fee', 'broker', 'kyc', 'verification',
            'stuck', 'pending', 'failed', 'error', 'bug', 'problem', 'issue', 'glitch', 'crash',
            'hang', 'slow', 'lag', 'server', 'loading', 'login', 'otp', 'password', 'finger',
            'biometric', 'notify', 'notification', 'support', 'help', 'care', 'call', 'email',
            'time', 'day', 'days', 'hour', 'hours', 'wait', 'waiting', 'process', 'showing',
            'wrong', 'correct', 'correctly', 'fake', 'scam', 'fraud', 'chart', 'candlestick',
            'timeframe', 'brokerage', 'balance', 'statement', 'download', 'upload'
        }

    def semantic_quality_check(self, text: str) -> bool:
        """
        A second-pass filtering step that looks for 'semantic' markers of 
        meaningful feedback (issues, experiences, or feature mentions).
        """
        clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        words = clean_text.split()
        
        if not words:
            return False

        # 1. Problem/Issue Intensity Markers
        # (Keywords that combined with others usually signal an issue)
        issue_markers = {
            'not', 'no', 'problem', 'issue', 'wrong', 'error', 'failed', 'stuck',
            'slow', 'lag', 'crash', 'bad', 'waste', 'worst', 'poor', 'expensive',
            'broken', 'missing', 'fake', 'fraud', 'scam', 'unable', 'cant', 'cannot',
            'nahi', 'kam', 'bekaar', 'kharaab'
        }
        
        # 2. Experiential/Action Markers
        # (Words indicating the user is describing an actual interaction)
        action_markers = {
            'using', 'tried', 'trying', 'opened', 'clicked', 'bought', 'sold', 
            'invested', 'added', 'removed', 'transferred', 'got', 'received',
            'showing', 'show', 'display', 'screen', 'button', 'time', 'process',
            'hai', 'tha', 'raha', 'kar', 'diya'
        }

        # Logic: A review is likely meaningful if:
        # a) It contains a high-signal finance/tech word (already checked in is_meaningful)
        # b) It contains an Issue Marker + Action Marker
        # c) It contains a subject/action + specific product behavior
        
        has_issue = any(word in issue_markers for word in words)
        has_action = any(word in action_markers for word in words)
        
        # If it has both an action and an issue, it's very high quality
        if has_issue and has_action:
            return True
            
        # Check for Typos of critical words (Simple fuzzy match for short words)
        # e.g. "widra" for "withdrawal"
        typo_targets = {'widra': 'withdrawal', 'withdrawl': 'withdrawal', 'kyc': 'kyc', 'stk': 'stock'}
        if any(typo in words for typo in typo_targets):
            return True

        return False

    def is_meaningful(self, text: str) -> bool:
        # Normalize text: lowercase and remove special characters but keep spaces
        clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        words = clean_text.split()
        
        if not words:
            return False

        # 1. Check for high-signal keywords (Direct Keep)
        if any(word in self.high_signal_keywords for word in words):
            return True

        # 2. Check for low-signal composition
        # If the review is purely made of low-signal keywords, it's NOT meaningful
        is_pure_low_signal = all(word in self.low_signal_keywords for word in words)
        if is_pure_low_signal:
            return False

        # 3. length heuristic
        if len(words) < 4:
            return False

        # 4. Semantic check for "Description of interaction"
        return self.semantic_quality_check(text)

    def is_emoji_or_punct_only(self, text: str) -> bool:
        # Check if contains at least one alphanumeric character
        return not any(char.isalnum() for char in text)

    def clean(self):
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input file not found: {self.input_path}")

        with open(self.input_path, 'r', encoding='utf-8') as f:
            raw_reviews = json.load(f)

        cleaned_reviews = []
        seen_texts = set()

        for review in raw_reviews:
            text = review.get('review_text', '').strip()

            # 1. Remove empty reviews
            if not text:
                continue

            # 4. Remove emoji-only or punctuation-only reviews
            if self.is_emoji_or_punct_only(text):
                continue

            # 2 & 3. Semantic & Keyword filtering
            if not self.is_meaningful(text):
                continue

            # 5. Remove duplicate reviews
            if text in seen_texts:
                continue
            
            seen_texts.add(text)
            cleaned_reviews.append(review)

        # 6. Limit dataset size
        final_reviews = cleaned_reviews[:300]

        output_data = {
            "review_count": len(final_reviews),
            "reviews": final_reviews
        }

        # Ensure output directory exists
        output_dir = os.path.dirname(self.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return len(final_reviews)
