"""Local anonymous pilot feedback analysis; never uploads respondent information."""
import argparse
import pandas as pd
from pilot import validate_feedback, feedback_summary

def main():
    parser=argparse.ArgumentParser(description="Aggregate anonymized pilot survey CSV locally")
    parser.add_argument("--feedback",required=True)
    args=parser.parse_args()
    df=pd.read_csv(args.feedback,dtype=str,keep_default_na=False)
    stats=feedback_summary(validate_feedback(df))
    print("Pilot results (aggregate only):")
    for key,value in stats.items():
        print(f"{key}: {value}")
    print("Responses are unverified participant statements, not purchases or subscriptions.")

if __name__=="__main__":
    main()
