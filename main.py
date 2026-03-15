import argparse
import sys
import os
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_config(key):
    return os.getenv(key) or st.secrets.get(key)

def main():
    # Validation
    gemini_key = get_config("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        print("WARNING: GEMINI_API_KEY is missing from both environment variables and st.secrets.")
    parser = argparse.ArgumentParser(description="App Review Weekly Pulse Pipeline")
    parser.add_argument('--phase', type=str, choices=['collect', 'clean', 'analyze', 'insight', 'pulse', 'email'], help="Phase to run")
    parser.add_argument('--send', action='store_true', help="Enable SMTP email delivery for Phase 6")
    parser.add_argument('--recipient', type=str, help="Recipient email address for Phase 6")
    args = parser.parse_args()

    if args.phase == 'collect':
        print("Starting Phase 1: Review Collection...")
        from phase1_review_collection.services.collector import PlayStoreCollector
        collector = PlayStoreCollector('com.nextbillion.groww')
        run_id, output_path = collector.collect()
        print(f"Collection complete. Run ID: {run_id}")
        print(f"Data saved to: {output_path}")
        
    elif args.phase == 'clean':
        print("Starting Phase 2: Review Cleaning...")
        from phase2_review_cleaning.services.cleaner import ReviewCleaner
        input_file = "phase1_review_collection/raw_reviews.json"
        output_file = "phase2_review_cleaning/filtered_reviews.json"
        
        cleaner = ReviewCleaner(input_file, output_file)
        count = cleaner.clean()
        print(f"Cleaning complete. {count} reviews saved to {output_file}")
        
    elif args.phase == 'analyze':
        print("Starting Phase 3: Theme Analysis (Groq LLM)...")
        from phase3_theme_analysis.services.analyzer import ThemeAnalyzer
        input_file = "phase2_review_cleaning/filtered_reviews.json"
        output_file = "phase3_theme_analysis/theme_map.json"
        
        analyzer = ThemeAnalyzer(input_file, output_file)
        themes_count, reviews_count = analyzer.analyze()
        print(f"Analysis complete. Classified {reviews_count} reviews into {themes_count} themes.")
        print(f"Data saved to: {output_file}")
        
    elif args.phase == 'insight':
        print("Starting Phase 4: Insight Generation (Groq LLM)...")
        from phase4_insight_generation.services.insight_generator import InsightGenerator
        input_file = "phase3_theme_analysis/theme_map.json"
        output_file = "phase4_insight_generation/insights.json"
        
        generator = InsightGenerator(input_file, output_file)
        output_data = generator.generate()
        if output_data:
            print(f"Insight generation complete. Generated {len(output_data.get('action_ideas', []))} action ideas for {len(output_data.get('themes', []))} themes.")
        print(f"Data saved to: {output_file}")
        
    elif args.phase == 'pulse':
        print("Starting Phase 5: Weekly Pulse Generation (Gemini LLM)...")
        from phase5_weekly_pulse.services.pulse_generator import PulseGenerator
        theme_map = "phase3_theme_analysis/theme_map.json"
        insights = "phase4_insight_generation/insights.json"
        out_md = "phase5_weekly_pulse/weekly_pulse.md"
        out_txt = "phase5_weekly_pulse/weekly_pulse.txt"
        
        generator = PulseGenerator(theme_map, insights, out_md, out_txt)
        md, txt = generator.generate()
        print("Pulse generation complete.")
        print(f"Data saved to: {out_md}\nand: {out_txt}")
        
    elif args.phase == 'email':
        print("Starting Phase 6: Email Draft & Delivery...")
        from phase6_email_delivery.services.email_sender import EmailSender
        input_pulse = "phase5_weekly_pulse/weekly_pulse.md"
        out_draft_md = "phase6_email_delivery/email_draft.md"
        out_draft_txt = "phase6_email_delivery/email_draft.txt"
        
        sender = EmailSender(input_pulse, out_draft_md, out_draft_txt)
        sender.process(send_mode=args.send, recipient=args.recipient)
        
    else:
        print("Please specify a valid phase. Example: --phase collect")
        sys.exit(1)

if __name__ == "__main__":
    main()
