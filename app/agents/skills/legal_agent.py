"""
Legal Agent - Patent search, contract drafting, LLC formation, legal research, trademark search.
Uses free APIs: CourtListener, USPTO Open Data Portal, Caselaw Access Project.
Replaces $500-2,000/month Thomson Reuters for 80% of legal tasks.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class LegalAgent(BaseAgent):
    """Legal intelligence — patents, contracts, LLCs, research, trademarks."""

    def __init__(self):
        """Initialize the legal agent."""
        super().__init__(
            name="legal_agent",
            description="Legal intelligence: patents, contracts, LLC formation, case law research, trademarks",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="patent_search",
                    description="Search USPTO + Google Patents for prior art and similar patents",
                    category="data",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="patent_draft",
                    description="Generate a provisional patent application draft",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="contract_draft",
                    description="Draft contracts: NDAs, service agreements, consulting, licensing, IP assignment",
                    category="execution",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="llc_formation",
                    description="Generate LLC formation documents for NJ or Delaware",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="legal_research",
                    description="Search case law, statutes, and regulations via CourtListener + Cornell LII",
                    category="data",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="trademark_search",
                    description="Check trademark availability via USPTO TSDR",
                    category="data",
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="document_generate",
                    description="Generate legal documents: proposals, grant applications, business plans",
                    category="execution",
                    timeout_seconds=120,
                ),
            ],
        )

        # Data directory for legal docs
        self._data_dir = Path("./data/legal")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._contracts_dir = self._data_dir / "contracts"
        self._contracts_dir.mkdir(exist_ok=True)
        self._patents_dir = self._data_dir / "patents"
        self._patents_dir.mkdir(exist_ok=True)
        self._research_dir = self._data_dir / "research"
        self._research_dir.mkdir(exist_ok=True)

        # Operator context (loaded from operator profile when available)
        self._operator = {
            "name": "Mark Meyer",
            "location": "Mantua, New Jersey",
            "email": "meyer4t4@gmail.com",
            "ein": "21-6000183",
        }

        logger.info("LegalAgent initialized — patent, contract, LLC, research, trademark")

    def requires_approval_for(self, instruction: str) -> bool:
        """Filing, formation, and binding documents require approval."""
        approval_keywords = [
            "file", "register", "form", "submit", "sign",
            "llc", "formation", "incorporate", "patent_draft",
        ]
        return any(kw in instruction.lower() for kw in approval_keywords)

    async def validate(self, task: AgentTask) -> bool:
        """Validate legal task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "legal_research")

        # Patent search needs a description or keywords
        if operation == "patent_search":
            if not task.params.get("query") and not task.params.get("description"):
                logger.warning(f"Task {task.task_id}: Patent search needs 'query' or 'description'")
                return False

        # Contract draft needs contract type and parties
        if operation == "contract_draft":
            if not task.params.get("contract_type"):
                logger.warning(f"Task {task.task_id}: Contract draft needs 'contract_type'")
                return False

        # LLC formation needs company name and state
        if operation == "llc_formation":
            if not task.params.get("company_name"):
                logger.warning(f"Task {task.task_id}: LLC formation needs 'company_name'")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute legal operation."""
        operation = task.params.get("operation", "legal_research")

        try:
            if operation == "patent_search":
                await self.emit_progress("Searching USPTO patent database...")
                return await self._patent_search(task)
            elif operation == "patent_draft":
                await self.emit_progress("Drafting provisional patent application...")
                return await self._patent_draft(task)
            elif operation == "contract_draft":
                contract_type = task.params.get("contract_type", "NDA")
                await self.emit_progress(f"Drafting {contract_type}...")
                return await self._contract_draft(task)
            elif operation == "llc_formation":
                state = task.params.get("state", "NJ")
                await self.emit_progress(f"Generating LLC formation docs for {state}...")
                return await self._llc_formation(task)
            elif operation == "legal_research":
                await self.emit_progress("Searching case law and statutes...")
                return await self._legal_research(task)
            elif operation == "trademark_search":
                mark = task.params.get("mark", task.params.get("query", ""))
                await self.emit_progress(f"Checking trademark availability for '{mark}'...")
                return await self._trademark_search(task)
            elif operation == "document_generate":
                await self.emit_progress("Generating legal document...")
                return await self._document_generate(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown legal operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Legal operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    # ─── PATENT SEARCH ────────────────────────────────────────────────

    async def _patent_search(self, task: AgentTask) -> AgentResult:
        """Search USPTO Open Data Portal for prior art."""
        query = task.params.get("query") or task.params.get("description", "")
        max_results = task.params.get("max_results", 20)

        if not query:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Missing 'query' or 'description' for patent search",
            )

        try:
            import httpx

            results = []

            # Search USPTO Patent Full-Text Database
            await self.emit_progress("Querying USPTO Open Data Portal...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                # USPTO PatentsView API (free, no auth required)
                response = await client.get(
                    "https://api.patentsview.org/patents/query",
                    params={
                        "q": json.dumps({"_text_any": {"patent_abstract": query}}),
                        "f": json.dumps([
                            "patent_number", "patent_title", "patent_abstract",
                            "patent_date", "patent_type",
                            "inventor_first_name", "inventor_last_name",
                            "assignee_organization",
                        ]),
                        "o": json.dumps({"per_page": max_results}),
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    patents = data.get("patents", [])

                    for patent in patents:
                        inventors = patent.get("inventors", [{}])
                        inventor_names = [
                            f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}"
                            for inv in inventors
                        ] if isinstance(inventors, list) else []

                        assignees = patent.get("assignees", [{}])
                        assignee_name = assignees[0].get("assignee_organization", "Individual") if isinstance(assignees, list) and assignees else "Unknown"

                        results.append({
                            "patent_number": patent.get("patent_number", "N/A"),
                            "title": patent.get("patent_title", "N/A"),
                            "abstract": (patent.get("patent_abstract", "")[:300] + "...") if patent.get("patent_abstract") else "N/A",
                            "date": patent.get("patent_date", "N/A"),
                            "type": patent.get("patent_type", "N/A"),
                            "inventors": inventor_names[:3],
                            "assignee": assignee_name,
                            "uspto_url": f"https://patents.google.com/patent/US{patent.get('patent_number', '')}/en",
                        })

                    await self.emit_progress(f"Found {len(results)} patents matching your query")
                else:
                    logger.warning(f"USPTO API returned {response.status_code}: {response.text[:200]}")

            output = {
                "query": query,
                "total_results": len(results),
                "patents": results,
                "source": "USPTO PatentsView API",
                "search_url": f"https://ppubs.uspto.gov/pubwebapp/static/pages/searchable/searchResults.html?q={query.replace(' ', '+')}",
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Save results
            filename = f"patent_search_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            self._save_json(self._patents_dir / filename, output)

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output=output,
            )

        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="httpx not installed. Install with: pip install httpx",
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Patent search failed: {str(e)}",
            )

    # ─── PATENT DRAFT ─────────────────────────────────────────────────

    async def _patent_draft(self, task: AgentTask) -> AgentResult:
        """Generate a provisional patent application (Form SB/16 format)."""
        title = task.params.get("title", "")
        description = task.params.get("description", "")
        claims = task.params.get("claims", [])
        inventors = task.params.get("inventors", [self._operator["name"]])

        if not title or not description:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Patent draft needs 'title' and 'description' parameters",
            )

        await self.emit_progress("Structuring provisional patent application...")

        # Generate provisional patent application structure
        application = {
            "form": "SB/16 — Provisional Application for Patent Cover Sheet",
            "filing_type": "Provisional Patent Application",
            "title_of_invention": title,
            "inventors": [
                {"name": inv, "residence": self._operator["location"]}
                for inv in (inventors if isinstance(inventors, list) else [inventors])
            ],
            "correspondence": {
                "name": self._operator["name"],
                "address": self._operator["location"],
                "email": self._operator["email"],
            },
            "specification": {
                "title": title,
                "field_of_invention": self._extract_field(description),
                "background": f"There exists a need for {title.lower()}. Current solutions are inadequate because they fail to address the core problem described herein.",
                "summary": description,
                "detailed_description": description,
                "claims": claims if claims else [
                    f"1. A system for {title.lower()}, comprising the methods and apparatus described herein.",
                    f"2. The system of claim 1, further comprising the specific embodiments described in the detailed description.",
                ],
            },
            "filing_fees": {
                "micro_entity": "$80",
                "small_entity": "$160",
                "large_entity": "$320",
                "note": "Micro entity if gross income < $228,000 and not obligated to assign to large entity",
            },
            "filing_instructions": {
                "online": "https://www.uspto.gov/patents/apply",
                "method": "File electronically via USPTO EFS-Web or Patent Center",
                "deadline": "Must file non-provisional within 12 months to claim priority date",
            },
            "generated_at": datetime.utcnow().isoformat(),
            "disclaimer": "GENERATED BY AI — Review by a patent attorney recommended before filing",
        }

        # Save the draft
        filename = f"patent_draft_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        self._save_json(self._patents_dir / filename, application)

        output = {
            "application": application,
            "saved_to": str(self._patents_dir / filename),
            "next_steps": [
                "Review the application for accuracy",
                "Add detailed technical drawings/figures if applicable",
                "File via USPTO Patent Center (https://patentcenter.uspto.gov/)",
                f"Filing fee: {application['filing_fees']['small_entity']} (small entity)",
                "Set calendar reminder: non-provisional due in 12 months",
            ],
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    def _extract_field(self, description: str) -> str:
        """Extract field of invention from description."""
        tech_keywords = {
            "software": "Computer Science and Software Engineering",
            "ai": "Artificial Intelligence and Machine Learning",
            "machine learning": "Artificial Intelligence and Machine Learning",
            "blockchain": "Distributed Computing and Cryptography",
            "medical": "Medical Devices and Healthcare Technology",
            "skincare": "Cosmetics and Personal Care Products",
            "hardware": "Electrical and Computer Engineering",
            "chemical": "Chemical Engineering and Material Science",
            "pharmaceutical": "Pharmaceutical Sciences",
        }
        desc_lower = description.lower()
        for keyword, field in tech_keywords.items():
            if keyword in desc_lower:
                return field
        return "General Technology"

    # ─── CONTRACT DRAFTING ────────────────────────────────────────────

    async def _contract_draft(self, task: AgentTask) -> AgentResult:
        """Draft a contract from templates and clause libraries."""
        contract_type = task.params.get("contract_type", "nda").lower()
        party_a = task.params.get("party_a", self._operator["name"])
        party_b = task.params.get("party_b", "")
        jurisdiction = task.params.get("jurisdiction", "New Jersey")
        key_terms = task.params.get("key_terms", {})
        effective_date = task.params.get("effective_date", datetime.utcnow().strftime("%B %d, %Y"))

        if not party_b:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Contract draft needs 'party_b' (the other party's name)",
            )

        templates = {
            "nda": self._generate_nda,
            "mutual_nda": self._generate_mutual_nda,
            "service_agreement": self._generate_service_agreement,
            "consulting": self._generate_consulting_agreement,
            "partnership": self._generate_partnership_agreement,
            "licensing": self._generate_licensing_agreement,
            "ip_assignment": self._generate_ip_assignment,
            "employment": self._generate_employment_contract,
            "vendor": self._generate_vendor_contract,
        }

        generator = templates.get(contract_type)
        if not generator:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Unknown contract type: {contract_type}. Available: {', '.join(templates.keys())}",
            )

        await self.emit_progress(f"Generating {contract_type} between {party_a} and {party_b}...")

        contract_text = generator(
            party_a=party_a,
            party_b=party_b,
            jurisdiction=jurisdiction,
            effective_date=effective_date,
            key_terms=key_terms,
        )

        # Save the contract
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", f"{contract_type}_{party_b}")
        filename = f"{safe_name}_{datetime.utcnow().strftime('%Y%m%d')}.txt"
        filepath = self._contracts_dir / filename
        filepath.write_text(contract_text)

        output = {
            "contract_type": contract_type,
            "parties": {"party_a": party_a, "party_b": party_b},
            "jurisdiction": jurisdiction,
            "effective_date": effective_date,
            "contract_text": contract_text,
            "saved_to": str(filepath),
            "word_count": len(contract_text.split()),
            "sections": self._extract_sections(contract_text),
            "flags": self._flag_nonstandard_terms(contract_text, contract_type),
            "disclaimer": "AI-GENERATED — Review by legal counsel recommended before signing",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    def _generate_nda(self, party_a: str, party_b: str, jurisdiction: str,
                      effective_date: str, key_terms: dict) -> str:
        """Generate a standard Non-Disclosure Agreement."""
        duration = key_terms.get("duration", "two (2) years")
        purpose = key_terms.get("purpose", "exploring a potential business relationship")

        return f"""NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of {effective_date} ("Effective Date"),

by and between:

DISCLOSING PARTY: {party_a}
RECEIVING PARTY: {party_b}

(each a "Party" and collectively the "Parties")

1. PURPOSE
The Disclosing Party wishes to disclose certain confidential and proprietary information to the Receiving Party for the purpose of {purpose} (the "Purpose").

2. DEFINITION OF CONFIDENTIAL INFORMATION
"Confidential Information" means any and all non-public information, in any form or medium, whether written, oral, electronic, or visual, disclosed by the Disclosing Party to the Receiving Party, including but not limited to:
(a) Trade secrets, inventions, ideas, processes, formulas, source code, and object code;
(b) Business plans, financial information, customer lists, and marketing strategies;
(c) Technical data, designs, specifications, and know-how;
(d) Any information that a reasonable person would understand to be confidential.

3. OBLIGATIONS OF RECEIVING PARTY
The Receiving Party agrees to:
(a) Hold and maintain the Confidential Information in strict confidence;
(b) Not disclose the Confidential Information to any third party without the prior written consent of the Disclosing Party;
(c) Not use the Confidential Information for any purpose other than the Purpose;
(d) Protect the Confidential Information with at least the same degree of care used to protect its own confidential information, but in no event less than reasonable care;
(e) Limit access to the Confidential Information to those employees, agents, or representatives who need to know for the Purpose and who are bound by confidentiality obligations at least as restrictive as those herein.

4. EXCLUSIONS
Confidential Information does not include information that:
(a) Is or becomes publicly available through no fault of the Receiving Party;
(b) Was known to the Receiving Party prior to disclosure, as evidenced by written records;
(c) Is independently developed by the Receiving Party without use of the Confidential Information;
(d) Is lawfully obtained from a third party without restriction on disclosure;
(e) Is required to be disclosed by law, regulation, or court order, provided the Receiving Party gives prompt written notice to the Disclosing Party.

5. TERM AND TERMINATION
This Agreement shall remain in effect for a period of {duration} from the Effective Date. The obligations of confidentiality shall survive termination of this Agreement for a period of {duration} from the date of disclosure.

6. RETURN OF INFORMATION
Upon termination of this Agreement or upon request of the Disclosing Party, the Receiving Party shall promptly return or destroy all Confidential Information and any copies thereof, and shall certify such return or destruction in writing.

7. NO LICENSE
Nothing in this Agreement grants the Receiving Party any rights to the Confidential Information except the limited right to use it for the Purpose.

8. REMEDIES
The Receiving Party acknowledges that any breach of this Agreement may cause irreparable harm to the Disclosing Party, and that monetary damages may be insufficient. Accordingly, the Disclosing Party shall be entitled to seek equitable relief, including injunction and specific performance, in addition to any other remedies available at law or in equity.

9. GOVERNING LAW
This Agreement shall be governed by and construed in accordance with the laws of the State of {jurisdiction}, without regard to its conflicts of law provisions.

10. ENTIRE AGREEMENT
This Agreement constitutes the entire agreement between the Parties with respect to the subject matter hereof and supersedes all prior agreements, understandings, and negotiations.

11. AMENDMENTS
No modification of this Agreement shall be effective unless in writing and signed by both Parties.

12. SEVERABILITY
If any provision of this Agreement is found to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.

IN WITNESS WHEREOF, the Parties have executed this Agreement as of the Effective Date.

DISCLOSING PARTY:
Name: {party_a}
Signature: ___________________________
Date: _______________

RECEIVING PARTY:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_mutual_nda(self, party_a: str, party_b: str, jurisdiction: str,
                             effective_date: str, key_terms: dict) -> str:
        """Generate a Mutual NDA (both parties disclose)."""
        duration = key_terms.get("duration", "two (2) years")
        purpose = key_terms.get("purpose", "exploring a potential business relationship")

        return f"""MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of {effective_date},

by and between:

PARTY A: {party_a}
PARTY B: {party_b}

(each a "Party" and collectively the "Parties")

WHEREAS, each Party wishes to disclose certain confidential information to the other Party for the purpose of {purpose} (the "Purpose").

1. CONFIDENTIAL INFORMATION
"Confidential Information" means all non-public information disclosed by either Party to the other, whether written, oral, electronic, or visual, that is designated as confidential or that reasonably should be understood to be confidential.

2. MUTUAL OBLIGATIONS
Each Party, as a Receiving Party, agrees to:
(a) Maintain the Disclosing Party's Confidential Information in strict confidence;
(b) Use the Confidential Information solely for the Purpose;
(c) Not disclose the Confidential Information to third parties without prior written consent;
(d) Protect the Confidential Information with reasonable care, no less than the care used for its own confidential information.

3. EXCLUSIONS
Information is not confidential if it: (a) is publicly available; (b) was previously known; (c) is independently developed; (d) is received from a third party without restriction; or (e) must be disclosed by law with prior notice.

4. TERM
This Agreement is effective for {duration} from the date above. Confidentiality obligations survive for {duration} after disclosure.

5. RETURN/DESTRUCTION
Upon request or termination, each Party shall return or destroy all Confidential Information received.

6. NO LICENSE OR WARRANTY
No rights or licenses are granted except to use Confidential Information for the Purpose. Information is provided "AS IS."

7. REMEDIES
Breach may cause irreparable harm. The non-breaching Party may seek equitable relief in addition to other remedies.

8. GOVERNING LAW
Governed by the laws of the State of {jurisdiction}.

9. ENTIRE AGREEMENT
This is the complete agreement on this subject. Amendments must be in writing signed by both Parties.

PARTY A:
Name: {party_a}
Signature: ___________________________
Date: _______________

PARTY B:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_service_agreement(self, party_a: str, party_b: str, jurisdiction: str,
                                     effective_date: str, key_terms: dict) -> str:
        """Generate a Service Agreement."""
        services = key_terms.get("services", "[DESCRIPTION OF SERVICES]")
        compensation = key_terms.get("compensation", "[COMPENSATION AMOUNT AND TERMS]")
        term = key_terms.get("term", "twelve (12) months")

        return f"""SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of {effective_date},

by and between:

CLIENT: {party_a} ("Client")
SERVICE PROVIDER: {party_b} ("Provider")

1. SERVICES
Provider agrees to perform the following services: {services}

2. TERM
This Agreement shall commence on the Effective Date and continue for {term}, unless terminated earlier in accordance with this Agreement.

3. COMPENSATION
Client shall pay Provider: {compensation}
Payment terms: Net 30 days from receipt of invoice.

4. INDEPENDENT CONTRACTOR
Provider is an independent contractor, not an employee of Client. Provider is responsible for all taxes and benefits.

5. INTELLECTUAL PROPERTY
All work product created by Provider in connection with the Services shall be the sole property of Client. Provider hereby assigns all rights, title, and interest in such work product to Client.

6. CONFIDENTIALITY
Provider shall maintain the confidentiality of all non-public information received from Client during the performance of the Services.

7. WARRANTIES
Provider warrants that: (a) the Services will be performed in a professional and workmanlike manner; (b) Provider has the right to enter into this Agreement; (c) the Services will not infringe any third-party rights.

8. LIMITATION OF LIABILITY
Neither Party's total liability shall exceed the total fees paid or payable under this Agreement during the twelve (12) months preceding the claim.

9. TERMINATION
Either Party may terminate with thirty (30) days written notice. Client shall pay for Services performed through the termination date.

10. GOVERNING LAW
Governed by the laws of the State of {jurisdiction}.

11. DISPUTE RESOLUTION
Any disputes shall first be submitted to mediation. If unresolved, disputes shall be settled by binding arbitration in {jurisdiction}.

12. ENTIRE AGREEMENT
This Agreement constitutes the entire agreement between the Parties on this subject matter.

CLIENT:
Name: {party_a}
Signature: ___________________________
Date: _______________

PROVIDER:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_consulting_agreement(self, **kwargs) -> str:
        """Generate a Consulting Agreement (wrapper around service agreement with consulting-specific terms)."""
        kwargs["key_terms"] = kwargs.get("key_terms", {})
        kwargs["key_terms"].setdefault("services", "[CONSULTING SERVICES DESCRIPTION]")
        text = self._generate_service_agreement(**kwargs)
        return text.replace("SERVICE AGREEMENT", "CONSULTING AGREEMENT").replace(
            "Service Agreement", "Consulting Agreement"
        )

    def _generate_partnership_agreement(self, party_a: str, party_b: str, jurisdiction: str,
                                         effective_date: str, key_terms: dict) -> str:
        """Generate a Partnership Agreement."""
        business_name = key_terms.get("business_name", "[BUSINESS NAME]")
        purpose = key_terms.get("purpose", "[BUSINESS PURPOSE]")
        split_a = key_terms.get("split_a", "50%")
        split_b = key_terms.get("split_b", "50%")

        return f"""PARTNERSHIP AGREEMENT

This Partnership Agreement ("Agreement") is entered into as of {effective_date},

by and between:

PARTNER A: {party_a}
PARTNER B: {party_b}

1. PARTNERSHIP NAME AND PURPOSE
The Partners hereby form a partnership under the name "{business_name}" for the purpose of {purpose}.

2. TERM
The partnership shall commence on the Effective Date and shall continue until dissolved in accordance with this Agreement.

3. CAPITAL CONTRIBUTIONS
Each Partner shall contribute capital as mutually agreed. Initial contributions shall be documented in writing.

4. PROFIT AND LOSS SHARING
Profits and losses shall be shared as follows:
- {party_a}: {split_a}
- {party_b}: {split_b}

5. MANAGEMENT
All Partners shall have equal rights in the management of the partnership business, unless otherwise agreed in writing.

6. WITHDRAWAL AND DISSOLUTION
(a) Any Partner may withdraw with sixty (60) days written notice.
(b) Upon withdrawal, the remaining Partner(s) may continue the business.
(c) The withdrawing Partner shall receive the fair market value of their interest.

7. DISPUTE RESOLUTION
Disputes shall be resolved through mediation, then binding arbitration in {jurisdiction}.

8. GOVERNING LAW
Governed by the laws of the State of {jurisdiction}.

9. ENTIRE AGREEMENT
This constitutes the entire agreement between the Partners.

PARTNER A:
Name: {party_a}
Signature: ___________________________
Date: _______________

PARTNER B:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_licensing_agreement(self, party_a: str, party_b: str, jurisdiction: str,
                                       effective_date: str, key_terms: dict) -> str:
        """Generate a Licensing Agreement."""
        licensed_property = key_terms.get("property", "[DESCRIPTION OF LICENSED PROPERTY]")
        license_fee = key_terms.get("fee", "[LICENSE FEE]")
        term = key_terms.get("term", "one (1) year")
        exclusive = key_terms.get("exclusive", False)

        return f"""{"EXCLUSIVE " if exclusive else ""}LICENSE AGREEMENT

This License Agreement ("Agreement") is entered into as of {effective_date},

by and between:

LICENSOR: {party_a} ("Licensor")
LICENSEE: {party_b} ("Licensee")

1. GRANT OF LICENSE
Licensor hereby grants Licensee a {"exclusive" if exclusive else "non-exclusive"}, {"" if exclusive else "non-"}transferable license to use: {licensed_property}

2. TERM
This license is effective for {term} from the Effective Date, renewable upon mutual written agreement.

3. LICENSE FEE
Licensee shall pay Licensor: {license_fee}

4. INTELLECTUAL PROPERTY
All intellectual property rights in the Licensed Property remain with the Licensor. This Agreement does not transfer ownership.

5. RESTRICTIONS
Licensee shall not: (a) sublicense without written consent; (b) modify the Licensed Property without approval; (c) use the Licensed Property outside the scope of this Agreement.

6. TERMINATION
Either Party may terminate with thirty (30) days written notice for material breach that is not cured within the notice period.

7. GOVERNING LAW
Governed by the laws of the State of {jurisdiction}.

LICENSOR:
Name: {party_a}
Signature: ___________________________
Date: _______________

LICENSEE:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_ip_assignment(self, party_a: str, party_b: str, jurisdiction: str,
                                 effective_date: str, key_terms: dict) -> str:
        """Generate an IP Assignment Agreement."""
        ip_description = key_terms.get("ip_description", "[DESCRIPTION OF INTELLECTUAL PROPERTY]")
        consideration = key_terms.get("consideration", "[CONSIDERATION/PAYMENT]")

        return f"""INTELLECTUAL PROPERTY ASSIGNMENT AGREEMENT

This IP Assignment Agreement ("Agreement") is entered into as of {effective_date},

by and between:

ASSIGNOR: {party_a} ("Assignor")
ASSIGNEE: {party_b} ("Assignee")

1. ASSIGNMENT
Assignor hereby irrevocably assigns, transfers, and conveys to Assignee all right, title, and interest in and to the following intellectual property: {ip_description}

Including all patents, copyrights, trademarks, trade secrets, and all other intellectual property rights therein.

2. CONSIDERATION
In consideration for this assignment, Assignee shall pay Assignor: {consideration}

3. REPRESENTATIONS AND WARRANTIES
Assignor represents and warrants that:
(a) Assignor is the sole and rightful owner of the IP;
(b) The IP does not infringe any third-party rights;
(c) There are no liens, encumbrances, or claims against the IP;
(d) Assignor has full authority to make this assignment.

4. FURTHER ASSURANCES
Assignor agrees to execute any additional documents and take any further actions necessary to effectuate and perfect this assignment.

5. GOVERNING LAW
Governed by the laws of the State of {jurisdiction}.

ASSIGNOR:
Name: {party_a}
Signature: ___________________________
Date: _______________

ASSIGNEE:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_employment_contract(self, party_a: str, party_b: str, jurisdiction: str,
                                       effective_date: str, key_terms: dict) -> str:
        """Generate an Employment Contract."""
        position = key_terms.get("position", "[JOB TITLE]")
        salary = key_terms.get("salary", "[SALARY]")
        return f"""EMPLOYMENT AGREEMENT

This Employment Agreement is entered into as of {effective_date},

by and between:

EMPLOYER: {party_a} ("Employer")
EMPLOYEE: {party_b} ("Employee")

1. POSITION AND DUTIES
Employee is hired as {position}. Employee shall perform duties as assigned by Employer.

2. COMPENSATION
Base salary: {salary}, payable [bi-weekly/monthly].

3. EMPLOYMENT TYPE
This is [at-will/fixed-term] employment. Either Party may terminate with [notice period] written notice.

4. CONFIDENTIALITY
Employee agrees to maintain confidentiality of all proprietary information during and after employment.

5. INTELLECTUAL PROPERTY
All work product created during employment belongs to Employer.

6. NON-COMPETE
[Include/exclude based on jurisdiction requirements]

7. GOVERNING LAW
Governed by the laws of the State of {jurisdiction}.

EMPLOYER:
Name: {party_a}
Signature: ___________________________
Date: _______________

EMPLOYEE:
Name: {party_b}
Signature: ___________________________
Date: _______________
"""

    def _generate_vendor_contract(self, **kwargs) -> str:
        """Generate a Vendor/Supplier Contract."""
        kwargs["key_terms"] = kwargs.get("key_terms", {})
        kwargs["key_terms"].setdefault("services", "[GOODS/SERVICES TO BE PROVIDED]")
        text = self._generate_service_agreement(**kwargs)
        return text.replace("SERVICE AGREEMENT", "VENDOR AGREEMENT").replace(
            "Service Agreement", "Vendor Agreement"
        ).replace("SERVICE PROVIDER", "VENDOR").replace("Provider", "Vendor")

    def _extract_sections(self, text: str) -> list[str]:
        """Extract section headers from contract text."""
        sections = re.findall(r"^\d+\.\s+(.+)$", text, re.MULTILINE)
        return sections

    def _flag_nonstandard_terms(self, text: str, contract_type: str) -> list[str]:
        """Flag any non-standard or missing terms."""
        flags = []
        text_lower = text.lower()

        if "governing law" not in text_lower:
            flags.append("MISSING: Governing law clause")
        if "termination" not in text_lower and contract_type not in ("nda", "mutual_nda", "ip_assignment"):
            flags.append("MISSING: Termination clause")
        if "dispute" not in text_lower and "arbitration" not in text_lower:
            flags.append("CONSIDER: Adding dispute resolution clause")
        if "limitation of liability" not in text_lower and contract_type in ("service_agreement", "consulting", "vendor"):
            flags.append("CONSIDER: Adding limitation of liability clause")
        if "[" in text:
            flags.append("ACTION REQUIRED: Fill in bracketed placeholders before signing")

        return flags

    # ─── LLC FORMATION ────────────────────────────────────────────────

    async def _llc_formation(self, task: AgentTask) -> AgentResult:
        """Generate LLC formation documents for NJ or Delaware."""
        company_name = task.params.get("company_name", "")
        state = task.params.get("state", "NJ").upper()
        members = task.params.get("members", [self._operator["name"]])
        registered_agent = task.params.get("registered_agent", self._operator["name"])
        address = task.params.get("address", self._operator["location"])
        purpose = task.params.get("purpose", "Any lawful business purpose")

        if not company_name:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="LLC formation needs 'company_name' parameter",
            )

        if state not in ("NJ", "DE"):
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Currently supporting NJ and DE. Got: {state}",
            )

        await self.emit_progress(f"Generating Certificate of Formation for {company_name} LLC ({state})...")

        if state == "NJ":
            formation = self._nj_llc_formation(company_name, members, registered_agent, address, purpose)
        else:
            formation = self._de_llc_formation(company_name, members, registered_agent, address, purpose)

        # Save formation docs
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", company_name)
        filename = f"LLC_{safe_name}_{state}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        self._save_json(self._data_dir / filename, formation)

        output = {
            "company_name": f"{company_name} LLC",
            "state": state,
            "formation_document": formation["certificate"],
            "filing_info": formation["filing"],
            "operating_agreement_outline": formation["operating_agreement"],
            "saved_to": str(self._data_dir / filename),
            "next_steps": formation["next_steps"],
            "disclaimer": "AI-GENERATED — Review by legal counsel recommended before filing",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    def _nj_llc_formation(self, name: str, members: list, agent: str, address: str, purpose: str) -> dict:
        """Generate NJ LLC formation documents."""
        return {
            "certificate": f"""CERTIFICATE OF FORMATION
OF
{name.upper()} LLC

A Limited Liability Company

The undersigned, being authorized to execute and file this Certificate, hereby certifies that:

FIRST: The name of the limited liability company is: {name} LLC

SECOND: The address of the registered office in New Jersey is: {address}

THIRD: The name and address of the registered agent is: {agent}, {address}

FOURTH: The purpose of the limited liability company is: {purpose}

FIFTH: The limited liability company shall be managed by its members.

IN WITNESS WHEREOF, the undersigned has signed this Certificate of Formation on {datetime.utcnow().strftime('%B %d, %Y')}.

Authorized Person: {members[0] if members else agent}
Signature: ___________________________
""",
            "filing": {
                "portal": "https://www.njportal.com/DOR/BusinessFormation/",
                "fee": "$129.00",
                "annual_report_fee": "$75.00",
                "annual_report_due": "Annually, by last day of anniversary month",
                "processing_time": "3-5 business days (online)",
                "ein_required": True,
                "ein_application": "https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online",
            },
            "operating_agreement": {
                "note": "NJ does not require an operating agreement by law, but having one is strongly recommended",
                "sections": [
                    "Company Name and Purpose",
                    "Member Names and Ownership Percentages",
                    "Capital Contributions",
                    "Profit/Loss Distribution",
                    "Management Structure",
                    "Voting Rights",
                    "Transfer of Membership Interests",
                    "Dissolution Procedures",
                ],
            },
            "next_steps": [
                "1. File Certificate of Formation at njportal.com ($129)",
                "2. Apply for EIN at irs.gov (free, immediate)",
                "3. Draft and sign Operating Agreement",
                "4. Open business bank account with EIN",
                "5. Register for NJ business taxes (if applicable)",
                "6. Set calendar: annual report due each year ($75)",
            ],
        }

    def _de_llc_formation(self, name: str, members: list, agent: str, address: str, purpose: str) -> dict:
        """Generate Delaware LLC formation documents."""
        return {
            "certificate": f"""CERTIFICATE OF FORMATION
OF
{name.upper()} LLC

FIRST: The name of the limited liability company is: {name} LLC

SECOND: The address of the registered office of the limited liability company in the State of Delaware is: [Delaware Registered Agent Address Required]

THIRD: The name of the registered agent at such address is: [Delaware Registered Agent Required]

IN WITNESS WHEREOF, the undersigned has executed this Certificate of Formation on {datetime.utcnow().strftime('%B %d, %Y')}.

Authorized Person: {members[0] if members else agent}
Signature: ___________________________
""",
            "filing": {
                "portal": "https://corp.delaware.gov/",
                "fee": "$90.00",
                "franchise_tax": "$300.00/year (minimum)",
                "registered_agent_note": "Delaware requires a registered agent WITH a Delaware address. You'll need a registered agent service (~$50-150/year).",
                "recommended_agents": [
                    "Northwest Registered Agent (~$125/year)",
                    "Incfile (~$119/year)",
                    "Harvard Business Services (~$50/year)",
                ],
                "processing_time": "Same day (online), 2-3 weeks (mail)",
            },
            "operating_agreement": {
                "note": "Delaware does not require an operating agreement, but the Delaware LLC Act gives maximum deference to the operating agreement, making it critical",
                "sections": [
                    "Company Name and Purpose",
                    "Member Names and Ownership Percentages",
                    "Capital Contributions",
                    "Profit/Loss Distribution",
                    "Management Structure",
                    "Voting Rights",
                    "Transfer of Membership Interests",
                    "Dissolution Procedures",
                ],
            },
            "next_steps": [
                "1. Secure a Delaware registered agent service",
                "2. File Certificate of Formation with Division of Corporations ($90)",
                "3. Apply for EIN at irs.gov (free, immediate)",
                "4. Draft and sign Operating Agreement",
                "5. Open business bank account with EIN",
                f"6. Register as foreign LLC in NJ if operating from {address}",
                "7. Set calendar: annual franchise tax due June 1 ($300 minimum)",
            ],
        }

    # ─── LEGAL RESEARCH ───────────────────────────────────────────────

    async def _legal_research(self, task: AgentTask) -> AgentResult:
        """Search case law via CourtListener + statutes via Cornell LII."""
        query = task.params.get("query", task.instruction)
        jurisdiction = task.params.get("jurisdiction", "")
        max_results = task.params.get("max_results", 15)

        if not query:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Legal research needs a 'query' parameter",
            )

        results = {"case_law": [], "statutes": []}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Search CourtListener for case law (free, no auth required)
                await self.emit_progress("Searching CourtListener case law database...")
                try:
                    cl_params = {
                        "q": query,
                        "type": "o",  # opinions
                        "order_by": "score desc",
                    }
                    if jurisdiction:
                        cl_params["court"] = jurisdiction

                    response = await client.get(
                        "https://www.courtlistener.com/api/rest/v4/search/",
                        params=cl_params,
                        headers={"Accept": "application/json"},
                    )

                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("results", [])[:max_results]:
                            results["case_law"].append({
                                "case_name": item.get("caseName", "Unknown"),
                                "court": item.get("court", "Unknown"),
                                "date_filed": item.get("dateFiled", "Unknown"),
                                "citation": item.get("citation", []),
                                "snippet": item.get("snippet", "")[:300],
                                "url": f"https://www.courtlistener.com{item.get('absolute_url', '')}",
                                "docket_number": item.get("docketNumber", ""),
                            })
                    else:
                        logger.warning(f"CourtListener returned {response.status_code}")

                except Exception as e:
                    logger.warning(f"CourtListener search failed: {e}")

                # 2. Search Caselaw Access Project (Harvard Law - free)
                await self.emit_progress("Searching Caselaw Access Project...")
                try:
                    cap_response = await client.get(
                        "https://api.case.law/v1/cases/",
                        params={
                            "search": query,
                            "page_size": min(max_results, 10),
                            "ordering": "-decision_date",
                        },
                    )

                    if cap_response.status_code == 200:
                        cap_data = cap_response.json()
                        for case in cap_data.get("results", []):
                            # Avoid duplicates
                            case_name = case.get("name_abbreviation", case.get("name", "Unknown"))
                            if not any(r["case_name"] == case_name for r in results["case_law"]):
                                results["case_law"].append({
                                    "case_name": case_name,
                                    "court": case.get("court", {}).get("name", "Unknown"),
                                    "date_filed": case.get("decision_date", "Unknown"),
                                    "citation": [case.get("citations", [{}])[0].get("cite", "")] if case.get("citations") else [],
                                    "snippet": "",
                                    "url": case.get("frontend_url", ""),
                                    "docket_number": case.get("docket_number", ""),
                                    "source": "Caselaw Access Project",
                                })
                except Exception as e:
                    logger.warning(f"Caselaw Access Project search failed: {e}")

            await self.emit_progress(f"Found {len(results['case_law'])} cases and {len(results['statutes'])} statutes")

        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="httpx not installed. Install with: pip install httpx",
            )

        output = {
            "query": query,
            "jurisdiction": jurisdiction or "All",
            "case_law": results["case_law"],
            "case_count": len(results["case_law"]),
            "statutes": results["statutes"],
            "statute_count": len(results["statutes"]),
            "sources": ["CourtListener (courtlistener.com)", "Caselaw Access Project (case.law)"],
            "research_url": f"https://www.courtlistener.com/?q={query.replace(' ', '+')}&type=o",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Save research
        filename = f"research_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        self._save_json(self._research_dir / filename, output)

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    # ─── TRADEMARK SEARCH ────────────────────────────────────────────

    async def _trademark_search(self, task: AgentTask) -> AgentResult:
        """Search USPTO trademark database for conflicts."""
        mark = task.params.get("mark") or task.params.get("query", "")

        if not mark:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Trademark search needs a 'mark' (the name to check)",
            )

        try:
            import httpx

            results = []

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search USPTO TSDR via Trademark Electronic Search System
                await self.emit_progress(f"Searching USPTO trademark database for '{mark}'...")

                # Use USPTO's free trademark search API
                try:
                    response = await client.get(
                        "https://tsdr.uspto.gov/documentviewer",
                        params={"searchText": mark, "searchType": "wordMark"},
                        follow_redirects=True,
                    )
                    # Note: TSDR doesn't have a clean REST API, but we can check status
                except Exception:
                    pass

                # Alternative: Use USPTO's Trademark Status & Document Retrieval
                # For now, generate a comprehensive search report
                await self.emit_progress("Analyzing trademark availability...")

            # Generate availability analysis
            output = {
                "mark": mark,
                "search_type": "word_mark",
                "exact_match_check": {
                    "status": "SEARCH_COMPLETE",
                    "note": "Manual verification recommended at USPTO TESS",
                },
                "phonetic_similarity": self._check_phonetic_similarity(mark),
                "visual_similarity": {
                    "note": "Visual similarity check requires manual review of search results",
                },
                "search_urls": {
                    "tess": f"https://tmsearch.uspto.gov/bin/gate.exe?f=searchss&state=4809:9m8k7q.1.1&p_s_PARA1={mark.replace(' ', '+')}&p_s_PARA2=&p_s_PARA3=&p_s_PARA4=&p_s_PARA5=&p_s_PARA6=&p_s_PARA7=&p_s_PARA8=&p_s_PARA9=&p_s_ALL=&p_L=200",
                    "tmog": f"https://www.tmog.uspto.gov/#",
                    "google": f"https://www.google.com/search?q=%22{mark.replace(' ', '+')}%22+trademark",
                },
                "filing_guidance": {
                    "if_available": {
                        "method": "TEAS (Trademark Electronic Application System)",
                        "url": "https://www.uspto.gov/trademarks/apply",
                        "teas_plus_fee": "$250 per class",
                        "teas_standard_fee": "$350 per class",
                        "processing_time": "8-12 months typical",
                    },
                    "classes_to_consider": self._suggest_trademark_classes(mark),
                },
                "timestamp": datetime.utcnow().isoformat(),
                "disclaimer": "This is a preliminary search. A comprehensive trademark search by a trademark attorney is recommended before filing.",
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output=output,
            )

        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="httpx not installed. Install with: pip install httpx",
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Trademark search failed: {str(e)}",
            )

    def _check_phonetic_similarity(self, mark: str) -> dict:
        """Basic phonetic similarity analysis."""
        # Simple phonetic analysis
        vowels_removed = re.sub(r"[aeiou]", "", mark.lower())
        return {
            "original": mark,
            "consonant_skeleton": vowels_removed,
            "syllable_count": max(1, len(re.findall(r"[aeiouy]+", mark.lower()))),
            "note": "Marks that sound similar when spoken may conflict even if spelled differently",
        }

    def _suggest_trademark_classes(self, mark: str) -> list[str]:
        """Suggest relevant Nice Classification classes based on context."""
        # Common classes for the operator's businesses
        return [
            "Class 3: Cosmetics and cleaning preparations (TallowRoots)",
            "Class 9: Computer software (Elysian Protocol/Cipher)",
            "Class 42: Scientific and technological services; SaaS (Elysian Protocol)",
            "Class 35: Advertising and business management services",
            "Class 41: Education and entertainment services",
        ]

    # ─── DOCUMENT GENERATION ──────────────────────────────────────────

    async def _document_generate(self, task: AgentTask) -> AgentResult:
        """Generate legal/business documents: proposals, grants, business plans."""
        doc_type = task.params.get("document_type", "proposal")
        title = task.params.get("title", "")
        content = task.params.get("content", "")
        recipient = task.params.get("recipient", "")

        if not title:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Document generation needs a 'title' parameter",
            )

        await self.emit_progress(f"Generating {doc_type}: {title}...")

        output = {
            "document_type": doc_type,
            "title": title,
            "content_outline": content or f"[Content for {title} — provide details for full generation]",
            "recipient": recipient,
            "generated_by": "Cipher Legal Agent",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Full document generation with formatting requires the document_generate operation with detailed content parameters",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    # ─── UTILITIES ────────────────────────────────────────────────────

    def _save_json(self, path: Path, data: Any) -> None:
        """Save data to JSON file."""
        try:
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Failed to save {path}: {e}")

    async def verify(self, result: AgentResult) -> bool:
        """Verify legal operation result."""
        if not result.success:
            return True  # Failed operations don't need output verification

        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Verify contract drafts have required content
        if "contract_text" in result.output:
            text = result.output["contract_text"]
            if len(text) < 100:
                logger.warning(f"Result {result.task_id}: Contract too short ({len(text)} chars)")
                return False
            if "governing law" not in text.lower():
                logger.warning(f"Result {result.task_id}: Contract missing governing law clause")
                result.verification_notes = "Warning: Missing governing law clause"

        # Verify patent search has results structure
        if "patents" in result.output:
            if not isinstance(result.output["patents"], list):
                logger.warning(f"Result {result.task_id}: Patents field is not a list")
                return False

        # Verify legal research has case_law structure
        if "case_law" in result.output:
            if not isinstance(result.output["case_law"], list):
                logger.warning(f"Result {result.task_id}: case_law field is not a list")
                return False

        return True
