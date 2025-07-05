"""
Command-line driver:
1. Load knowledge.txt into Neo4j
2. Diagnose patient
3. View last 10 audit events (Admin only)
4. Exit
"""
import time
import json
from neo4j_utils import (
    close, diseases_by_symptoms, create_diagnosis,
    log_audit, find_special_case, upsert_special_case, driver
)
from user_management import login_cli
from knowledge_loader import load as load_knowledge
from bayes_utils import diagnose, is_unusual
from Connection_check import check_neo4j_connection
from neo4j_utils import (
     close, diseases_by_symptoms, create_diagnosis,
    log_audit, find_special_case, upsert_special_case, driver,
     find_unknown_symptoms, upsert_special_case_with_patient,
          find_similar_special_cases, get_symptom_disease_probabilities  # Add these new imports
)

# ------------------------------ Admin ---------------------------------- #
def _admin_menu():
    """
    Show the 10 most recent audit events,
    printing the user name for USER_LOGIN actions.
    """
    try:
        with driver.session() as sess:
            recs = sess.run(
                """
                MATCH (a:Audit)
                RETURN a.action AS act, a.ts AS ts, a.details AS det
                ORDER BY ts DESC LIMIT 10
                """
            )
            for r in recs:
                details = json.loads(r["det"]) if r["det"] else {}
                if r["act"] == "USER_LOGIN":
                    who = details.get("name", "?")
                    print(f"{r['ts']}  USER_LOGIN  → {who}")
                else:
                    print(f"{r['ts']}  {r['act']}")
    except Exception as e:
        print(f"Error fetching audit logs: {e}")

def check_admin_password():
    """Ask for the admin password before giving access to admin features."""
    return input("Enter admin password: ").strip() == "12345"


# ----------------------------- Diagnosis ------------------------------- #
def diagnose_patient():
    """Interactive patient diagnosis with enhanced special case handling."""
    person = input("Patient name: ")
    syms = [
        s.strip().title()
        for s in input("List present symptoms comma-sep: ").split(",")
        if s.strip()
    ]

    # ——— Check for unknown symptoms ———
    unknown_syms = find_unknown_symptoms(syms)
    if unknown_syms:
        print(f"⚠️  Unknown symptoms detected: {', '.join(unknown_syms)}")
        print("These symptoms are not in the knowledge base and will be flagged as special case.")

        # Store as special case with patient info
        upsert_special_case_with_patient(syms, person)

        # Check for similar cases
        similar_cases = find_similar_special_cases(syms)
        if similar_cases:
            print(f"\n📋 Found {len(similar_cases)} similar special case(s):")
            for i, case in enumerate(similar_cases[:3], 1):  # Show top 3
                patients = case.get('patients', [])
                first_seen = time.strftime(
                    "%Y-%m-%d",
                    time.localtime(case.get("first_seen", 0) / 1000)
                )
                matched_symptoms = case.get('matched_symptoms', [])
                print(f"  {i}. Patients: {', '.join(patients)}")
                print(f"     First seen: {first_seen}, Hits: {case.get('hits', 1)}")
                print(f"     Matching symptoms: {', '.join(matched_symptoms)}")
                print()

    # ——— existing special-case bundle lookup ———
    sc = find_special_case(syms)
    if sc:
        first = time.strftime(
            "%Y-%m-%d",
            time.localtime(sc.get("first_seen", 0) / 1000)
        )
        patients = sc.get('patients', [])
        print(
            f"⚠️  Exact special-case bundle recognised!  "
            f"Seen {sc.get('hits', 1)} time(s), first on {first}."
        )
        if patients:
            print(f"   Previous patients: {', '.join(patients)}")

    # ——— Show symptom-disease probabilities ———
    print("\n📊 Symptom-Disease Probabilities:")
    for symptom in syms:
        if symptom not in unknown_syms:  # Only show for known symptoms
            probs = get_symptom_disease_probabilities(symptom)
            if probs:
                print(f"\n{symptom}:")
                for disease, prob in sorted(probs.items(), key=lambda x: -x[1]):
                    print(f"  {disease}: {prob * 100:.1f}%")

    # ——— choose match mode ———
    mode = input(
        "\nMatch mode – (a)ll symptoms, (p)artial ≥2, (w)ide ≥1  [a]: "
    ).strip().lower()
    if mode == "p":
        min_matches = 2
    elif mode == "w":
        min_matches = 1
    else:  # default "all"
        min_matches = None

    diseases = diseases_by_symptoms(syms, min_matches)

    # graceful fallback: if strict search empty → try ≥2 symptoms
    if not diseases and min_matches is None:
        diseases = diseases_by_symptoms(syms, 2)
        if diseases:
            print(
                "No disease matched *all* symptoms – "
                "showing diseases that match at least 2."
            )

    print(f"\n🏥 Diseases in KG matching criteria: {diseases or 'None'}")

    # Bayesian inference
    print("\n🧠 Bayesian Inference Results:")
    probs = diagnose(syms)
    for d, p in sorted(probs.items(), key=lambda x: -x[1]):
        confidence_level = "High" if p > 0.7 else "Medium" if p > 0.4 else "Low"
        print(f"{d}: {p * 100:.2f}% ({confidence_level} confidence)")

    # unusual-case handling
    if is_unusual(probs):
        print(
            "\n⚠️  Unusual case – storing as special bundle for future alerts."
        )
        upsert_special_case_with_patient(syms, person)
        log_audit("UNUSUAL_CASE", {"person": person, "symptoms": syms})

    # store best guess
    if probs:
        best = max(probs, key=probs.get)
        create_diagnosis(person, best, probs[best])
        print(f"\n✅ Recorded diagnosis: {best} for {person} (confidence: {probs[best] * 100:.1f}%)")
    else:
        print("\n⚠️  No diagnosis could be determined from available data.")


def show_main_menu():
    """Display the main menu options."""
    print("\n" + "="*50)
    print("     MEDICAL DIAGNOSIS SYSTEM")
    print("="*50)
    print("1) Load knowledge.txt into Neo4j")
    print("2) Diagnose patient")
    print("3) View last 10 audit events (Admin only)")
    print("4) Exit")
    print("="*50)


def show_diagnosis_menu():
    """Display options after completing a diagnosis."""
    print("\n" + "-"*40)
    print("     DIAGNOSIS COMPLETE")
    print("-"*40)
    print("What would you like to do next?")
    print("1) Diagnose another patient")
    print("2) Back to main menu")
    print("3) Exit program")
    print("-"*40)


def handle_diagnosis_flow():
    """Handle the diagnosis flow with enhanced navigation."""
    while True:
        try:
            # Perform diagnosis
            diagnose_patient()

            # Show post-diagnosis options
            while True:
                show_diagnosis_menu()
                choice = input("Enter your choice (1-3): ").strip()

                if choice == "1":
                    print("\n" + "="*30)
                    print("  DIAGNOSING NEW PATIENT")
                    print("="*30)
                    break  # Break inner loop to diagnose another patient

                elif choice == "2":
                    print("\nReturning to main menu...")
                    return "main_menu"  # Return to main menu

                elif choice == "3":
                    print("\nExiting program...")
                    return "exit"  # Exit program

                else:
                    print("❌ Invalid choice. Please select 1, 2, or 3.")

        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return "main_menu"
        except Exception as e:
            print(f"\n❌ Error during diagnosis: {e}")
            print("Returning to main menu...")
            return "main_menu"


# ----------------------------- Main loop ------------------------------- #
def main():
    try:
        username = login_cli()
        print(f"\n🎉 Welcome, {username}!")

        while True:
            show_main_menu()
            choice = input("Enter your choice (1-4): ").strip()

            if choice == "1":
                print("\n🔄 Loading knowledge base...")
                try:
                    load_knowledge()
                    print("✅ Knowledge base loaded successfully!")
                except Exception as e:
                    print(f"❌ Error loading knowledge base: {e}")

            elif choice == "2":
                print("\n🏥 Entering diagnosis mode...")
                result = handle_diagnosis_flow()
                if result == "exit":
                    break

            elif choice == "3":
                print("\n🔐 Admin access required...")
                if check_admin_password():
                    print("✅ Admin access granted")
                    print("\n📊 AUDIT LOG - Last 10 Events:")
                    print("-" * 50)
                    _admin_menu()
                else:
                    print("❌ Access denied - Invalid password")

            elif choice == "4":
                print("\n👋 Thank you for using the Medical Diagnosis System!")
                print("Goodbye!")
                break

            else:
                print("❌ Invalid choice. Please select 1, 2, 3, or 4.")

    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        print("\n🔌 Closing database connection...")
        close()
        print("✅ Database connection closed.")


if __name__ == "__main__":
    print("🔍 Checking Neo4j connection...")
    check_neo4j_connection()
    print("✅ Neo4j connection verified!")
    main()