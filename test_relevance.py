from relevance import score_job, is_relevant

targets = [
    'Associate Product Manager',
    'APM',
    'Junior PM',
    'Assistant Product Manager',
    'Product Analyst',
]

tests = [
    'Associate Product Manager',
    'Senior Product Manager',
    'Product Management Lead',
    'Portfolio Manager',
    'Business Development Manager',
    'APM - Associate Product Manager',
    'Product Analyst Intern',
    'Growth Product Manager',
    'Portfolio Management Specialist',
    'Junior Product Manager',
]

print(f"{'Job Title':<40} {'Score':>6}  {'Pass?'}")
print('-' * 58)
for title in tests:
    score   = score_job(title, targets)
    verdict = 'PASS' if is_relevant(title, targets) else 'FAIL'
    print(f"{title:<40} {score:>6.2f}  {verdict}")
