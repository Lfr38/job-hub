"""
Test per heuristic_filter — regressione keyword negative (RED).
Verifica che 'principal' non matchi 'principali', che 'lead' non matchi
'leading', ecc.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))

from heuristic_filter import calculate_heuristic_score


class TestNegativeKeywordWordBoundary:
    """Verifica che le keyword negative usino word boundary (RED)."""

    def test_principal_does_not_match_principali(self):
        """'principal' come parola inglese NON deve matchare l'italiano 'principali'."""
        score, status, details = calculate_heuristic_score(
            title="Cybersecurity Analyst",
            description="Responsabilità principali: monitoraggio reti, analisi incidenti, "
                         "gestione strumenti di sicurezza. Requisiti: conoscenza Python, "
                         "certificazioni Security+. Sede: Brescia.",
        )
        assert score >= 0, (
            f"ERRORE: 'principali' ha matchato la keyword 'principal'. "
            f"Score={score}, status={status}, reason={details.get('reason')}"
        )

    def test_principal_matches_standalone_english(self):
        """'Principal Engineer' deve MATCHARE la keyword 'principal'."""
        score, status, details = calculate_heuristic_score(
            title="Principal Security Engineer",
            description="Looking for a principal engineer to lead our security team.",
        )
        assert score == -1, (
            f"'Principal Engineer' deve essere rejected. Score={score}, status={status}"
        )

    def test_lead_does_not_match_leading(self):
        """'lead' come parola NON deve matchare 'leading' (gerundio o verbo)."""
        score, status, details = calculate_heuristic_score(
            title="Cybersecurity Analyst",
            description="You will be leading incident response and threat hunting activities.",
        )
        assert score >= 0, (
            f"ERRORE: 'leading' ha matchato 'lead'. Score={score}, status={status}"
        )

    def test_lead_matches_standalone(self):
        """'Lead Engineer' deve MATCHARE la keyword 'lead'."""
        score, status, details = calculate_heuristic_score(
            title="Lead Security Engineer",
            description="We are looking for a lead engineer.",
        )
        assert score == -1, (
            f"'Lead Engineer' deve essere rejected. Score={score}, status={status}"
        )

    def test_manager_does_not_match_management(self):
        """'manager' NON deve matchare 'management'."""
        score, status, details = calculate_heuristic_score(
            title="IT Support Specialist",
            description="Support the IT management team with daily operations.",
        )
        assert score >= 0, (
            f"ERRORE: 'management' ha matchato 'manager'. Score={score}, status={status}"
        )

    def test_manager_matches_standalone(self):
        """'Project Manager' deve MATCHARE 'manager'."""
        score, status, details = calculate_heuristic_score(
            title="Project Manager",
            description="Looking for a project manager.",
        )
        assert score == -1, (
            f"'Project Manager' deve essere rejected. Score={score}, status={status}"
        )

    def test_senior_does_not_match_seniority(self):
        """'senior' NON deve matchare 'seniority'."""
        score, status, details = calculate_heuristic_score(
            title="SOC Analyst",
            description="Great opportunity for growth in seniority.",
        )
        assert score >= 0, (
            f"ERRORE: 'seniority' ha matchato 'senior'. Score={score}, status={status}"
        )

    def test_senior_matches_standalone(self):
        """'Senior Developer' deve MATCHARE 'senior'."""
        score, status, details = calculate_heuristic_score(
            title="Senior Developer",
            description="Senior developer needed.",
        )
        assert score == -1, (
            f"'Senior Developer' deve essere rejected. Score={score}, status={status}"
        )

    def test_director_does_not_match_directory(self):
        """'director' NON deve matchare 'directory'."""
        score, status, details = calculate_heuristic_score(
            title="IT Support",
            description="Maintain Active Directory infrastructure.",
        )
        assert score >= 0, (
            f"ERRORE: 'directory' ha matchato 'director'. Score={score}, status={status}"
        )

    def test_five_plus_years_matches(self):
        """'5+ years' deve MATCHARE come keyword."""
        score, status, details = calculate_heuristic_score(
            title="Security Analyst",
            description="We require 5+ years of experience in cybersecurity.",
        )
        assert score == -1, (
            f"'5+ years' deve essere rejected. Score={score}, status={status}"
        )

    def test_five_years_without_plus_does_not_match(self):
        """'5 years' senza '+' NON deve matchare '5+ years'."""
        score, status, details = calculate_heuristic_score(
            title="Cybersecurity Analyst",
            description="Minimum 5 years experience required.",
        )
        # '5+ years' è la keyword → '5 years' senza '+' non dovrebbe matchare
        # (dipende dall'implementazione, ma con \b il '+' è richiesto)
        assert score >= 0, (
            f"'5 years' ha matchato '5+ years'. Score={score}, status={status}"
        )

    def test_junior_cybersecurity_passes(self):
        """'Junior Cyber Security' senza keyword negative deve passare."""
        score, status, details = calculate_heuristic_score(
            title="Junior Cyber Security Analyst",
            description="Junior position in cybersecurity. Python, SIEM, EDR. "
                         "Great team, mentorship, training provided. Brescia area.",
        )
        assert score > 0, (
            f"'Junior Cyber Security' deve avere score positivo. Score={score}, status={status}"
        )

    def test_head_of_does_not_match_heard_of(self):
        """'head of' NON deve matchare 'heard of'."""
        score, status, details = calculate_heuristic_score(
            title="Security Analyst",
            description="You might have heard of our company.",
        )
        assert score >= 0, (
            f"ERRORE: 'heard of' ha matchato 'head of'. Score={score}, status={status}"
        )

    def test_head_of_matches_standalone(self):
        """'Head of Security' deve MATCHARE 'head of'."""
        score, status, details = calculate_heuristic_score(
            title="Head of Security",
            description="Looking for a head of security.",
        )
        assert score == -1, (
            f"'Head of Security' deve essere rejected. Score={score}, status={status}"
        )
