import json

print("=== Job Search Setup ===\n")

job_title = input("1. What job title are you looking for? ").strip()
location_input = input("2. Preferred locations (comma-separated, e.g. Bangalore, Remote): ").strip()
location = [l.strip() for l in location_input.split(",") if l.strip()]

print("3. Experience level?")
print("   [1] Fresher")
print("   [2] 1-3 years")
print("   [3] 3-5 years")
print("   [4] 5+ years")
while True:
    choice = input("   Enter 1-4: ").strip()
    experience_map = {"1": "Fresher", "2": "1-3 years", "3": "3-5 years", "4": "5+ years"}
    if choice in experience_map:
        experience = experience_map[choice]
        break
    print("   Please enter a number between 1 and 4.")

skills_input = input("4. Key skills (comma-separated, e.g. Python, SQL, Excel): ").strip()
skills = [s.strip() for s in skills_input.split(",") if s.strip()]

salary_range = input("5. Preferred salary range (e.g. 40000-60000 or 'negotiable'): ").strip()

alt_input = input("6. Alternate job titles or abbreviations (comma-separated, e.g. APM, Junior PM): ").strip()
alternate_titles = [t.strip() for t in alt_input.split(",") if t.strip()]

config = {
    "job_title": job_title,
    "alternate_titles": alternate_titles,
    "location": location,
    "experience": experience,
    "skills": skills,
    "salary_range": salary_range
}

with open("config.json", "w") as f:
    json.dump(config, f, indent=2)

print("\n=== Saved to config.json ===")
print(json.dumps(config, indent=2))
