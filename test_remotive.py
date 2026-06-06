from remotive import fetch_jobs_remotive, parse_job_remotive
from relevance import score_job

titles = ['Associate Product Manager', 'APM', 'Junior PM', 'Assistant Product Manager', 'Product Analyst']
jobs, _ = fetch_jobs_remotive(titles, 'Remote')

print(f"{'Score':>6}  Job Title")
print('-' * 60)
for j in jobs:
    p     = parse_job_remotive(j)
    score = score_job(p['job_title'], titles)
    print(f"{score:.2f}   {p['job_title']}")
