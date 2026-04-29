---
name: bio-drug-paper-writing
description: Creates formal biomedical and pharmaceutical research papers following IMRAD structure and high-impact journal standards (Nature, Cell, NEJM, The Lancet). Use when the user asks to write a research paper on biotechnology, pharmaceuticals, drug discovery, clinical research, or biomedical science topics.
---

# Bio-Drug Paper Writer

## Overview

This skill guides the creation of formal biomedical and pharmaceutical research papers that meet publication standards for high-impact journals such as Nature, Cell, NEJM (New England Journal of Medicine), The Lancet, PNAS, and specialized journals like Journal of Medicinal Chemistry, Bioconjugate Chemistry, and Drug Discovery Today.

## Workflow

### 1. Understanding the Research Topic

When asked to write a bio/pharma research paper:

1. **Clarify the topic and scope** with the user:
   - What is the therapeutic area or disease target?
   - What is the drug candidate or biotechnology approach?
   - What is the stage of research (in vitro, in vivo, clinical, post-market)?
   - What is the target journal (impact factor, word limits)?
   - Are there specific sections required by the target journal?
   - What is the regulatory context (FDA, EMA, ICH guidelines)?

2. **Gather context** if needed:
   - Review any provided research materials, assay data, clinical trial results
   - Understand the biological pathway or mechanism of action
   - Identify key related work in the literature (PubMed, Scopus)
   - Note chemical structures, protein sequences, or clinical protocols

### 2. Paper Structure (IMRAD +)

Follow the IMRAD structure adapted for biomedical research:

```
1. Title
   - Concise, specific, containing key terms (drug name, target, disease)
   - Typically 10-15 words for high-impact journals
   - Avoid abbreviations in title unless well-known

2. Abstract (Structured for many journals)
   - Background / Objective (1-2 sentences)
   - Methods (2-3 sentences)
   - Results (3-4 sentences with key quantitative data)
   - Conclusions (1-2 sentences, clinical implications)
   - Word limit: 150-350 words depending on journal

3. Introduction
   - Disease burden and clinical need (epidemiology)
   - Current standard of care and limitations
   - Literature review of relevant prior work
   - Hypothesis and rationale for the study
   - Clear statement of objectives

4. Materials and Methods
   - Chemical synthesis or biological production details
   - Experimental models (cell lines, animal models, human subjects)
   - Assays and analytical methods with references
   - Statistical methods and power calculations
   - Regulatory approvals (IRB, IACUC, IND/CTA)

5. Results
   - Logical progression from primary to secondary endpoints
   - Include both positive and negative/null findings
   - Quantitative data with statistical significance
   - Figures and tables with clear legends
   - Supplementary materials reference

6. Discussion
   - Summary of key findings
   - Comparison with existing literature
   - Mechanistic interpretation
   - Clinical or translational implications
   - Strengths and limitations of the study
   - Future directions and next steps

7. Conclusion
   - Brief, impactful statement (often merged with Discussion)
   - Key take-home message
   - Clinical or policy implications if applicable

8. References
   - Journal-specific citation format
   - Prioritize recent literature (last 5 years) and landmark studies
   - Include appropriate preclinical and clinical references

9. Supplementary Materials (if applicable)
   - Extended methods
   - Additional figures and tables
   - Raw data
   - Chemical characterization data
```

### 3. Academic Writing Style for Biomedical Research

**Tone and Voice:**
- Formal, precise, objective language
- Third-person perspective for observational studies
- First-person permitted for describing own experimental work
- Past tense for completed experiments, present tense for established facts
- Humility in claims; avoid overstatement

**Biomedical Precision:**
- Define all abbreviations on first use: "vascular endothelial growth factor (VEGF)"
- Use standardized terminology (UniProt, HGNC, ChEBI, DrugBank)
- Report exact chemical names and structures
- Specify species, strain, sex of animals where relevant
- Include assay kit sources, catalog numbers, and lot numbers for reproducibility

**Argumentation:**
- Build logical case: disease → unmet need → prior approaches → gap → hypothesis → study → findings → implications
- Support claims with statistical evidence
- Discuss limitations openly
- Compare with both positive and negative literature

**Section-Specific Guidelines:**

*Abstract:*
- Structured abstracts preferred by many biomedical journals
- Include: Background/Aim, Methods, Results (with statistics), Conclusion
- Avoid vague qualifiers ("promising," "effective" without data)
- Self-contained (readable without the full paper)

*Introduction:*
- Open with disease burden and clinical relevance (cite epidemiological data)
- Narrow to specific knowledge gap
- State objectives using "Here we..." or "In this study we..." phrasing
- End with explicit aims or hypotheses

*Methods:*
- Be exhaustive for reproducibility
- Include: chemicals (vendor, purity), instruments (model, manufacturer), software (version, RRID)
- Describe statistical tests and significance thresholds
- Reference established protocols with DOI when possible

*Results:*
- Present data objectively without interpretation
- Use figures and tables effectively
- Report exact p-values, confidence intervals, effect sizes
- Include both statistical and clinical significance when relevant

*Discussion:*
- Start with principal finding
- Compare with published literature explicitly
- Discuss mechanism if relevant
- Acknowledge limitations
- End with translational or clinical implications

### 4. Formatting Guidelines

**Nature / Cell Press Format:**
- Page size: US Letter (8.5" × 11") or A4
- Margins: minimum 2.5cm all sides
- Font: Arial or Helvetica, 11pt for text, 9pt for figures
- Line spacing: Double spacing for main text (some journals prefer single)
- References: Numbered, superscript or in brackets

**NEJM / The Lancet Format:**
- Structured abstract required
- Methods may be in supplementary materials
- Word limits: strict (NEJM: 2,700 words for original articles)
- References: Vancouver style (numbered, not author-date)

**General Biomedical Paper Format:**
- Title page with: title, authors, affiliations, corresponding author contact
- Abstract page with keywords
- Main text with figure/table legends at end or integrated
- References with DOI preferred
- Supplementary materials appendix

### 5. Citations and References

**In-text citations (Vancouver/Nature style):**
- Superscript or bracketed numbers: "Recent work¹'² has shown..."
- Multiple citations in order of appearance
- Reference specific sections: "As demonstrated previously [5]"

**Reference formatting (Nature style example):**
```
[1] Author, A. B. & Author, C. D. Title of paper. Journal Name Volume, pages (Year).
[2] Author, E. F. et al. Title of book chapter. in Book Title (eds. Editor, G. H.) Vol. pages (Publisher, Year).
[3] Author, I. J. & Author, K. L. Title of conference proceeding. in Proc. Conf. Name, pages (Year).
```

**Reference list requirements:**
- Numbered in order of appearance
- Include all authors (or first 10 + et al. for very long lists)
- Include DOI or PubMed ID when available
- Minimum 30-50 references for a full paper in high-impact journals
- Prioritize primary literature over reviews
- Include appropriate landmark studies ( pivotal trials, foundational discoveries)

### 6. Bio/Pharma-Specific Considerations

**Drug Discovery Papers:**
- Include chemical structure rationale (if applicable)
- Report SAR (Structure-Activity Relationship) data
- Include ADMET properties (Absorption, Distribution, Metabolism, Excretion, Toxicity)
- Report IC50/EC50, Ki, Kd values with appropriate assay conditions
- Include purity and characterization data (NMR, MS, HPLC)

**Clinical Research Papers:**
- Register trial (ClinicalTrials.gov, EudraCT if applicable)
- Report CONSORT flow diagram elements
- Include power calculation and sample size justification
- Report adverse events comprehensively
- Include demographic data table
- Follow ICMJE authorship guidelines

**Biotechnology Papers:**
- Describe constructs and cloning strategies
- Report expression systems and conditions
- Include protein characterization (SDS-PAGE, Western, activity assays)
- Report yield, purity, stability data
- Describe formulation if applicable

**Regulatory Considerations:**
- Note IRB/IEC/IACUC approvals
- Include IND/CTA numbers if applicable
- Follow GPP (Good Publication Practice) guidelines
- Disclose funding sources and conflicts of interest
- Consider data availability statements

### 7. Content Generation Process

**Step-by-step approach:**

1. **Create outline**
   - Determine target journal and word limits
   - Develop detailed section-by-section outline
   - Define key figures and tables needed
   - Identify regulatory requirements

2. **Draft sections iteratively**
   - Start with Methods (most concrete)
   - Then Results (describe findings systematically)
   - Introduction (build case for the study)
   - Discussion (interpret findings)
   - Abstract last (summary of complete work)

3. **Add citations**
   - Reference related work throughout
   - Support claims with evidence from literature
   - Create comprehensive reference list with DOI

4. **Review and refine**
   - Check logical flow and scientific accuracy
   - Ensure consistency in terminology
   - Verify all figures/tables are referenced in text
   - Confirm abstract matches content
   - Check compliance with target journal guidelines

## Examples

**Example 1: User asks for a drug discovery paper**
```
User: "Write a research paper about our new CDK4/6 inhibitor for breast cancer"

Response:
1. Clarify scope: "I'll create a drug discovery paper on your CDK4/6 inhibitor. A few questions:
   - What is the compound code/name (e.g., ABC-123)?
   - What is the stage: in vitro, in vivo, or early clinical?
   - Target journal: Journal of Medicinal Chemistry, Cancer Research, or similar?
   - What SAR data is available?
   - Are there in vivo efficacy data?
   - Do you have selectivity data vs. other kinases?"

2. After clarification, structure as drug discovery paper:
   - Introduction: breast cancer burden, CDK4/6 role, need for new inhibitors
   - Chemistry: synthesis route, SAR exploration
   - Biology: enzyme assays, cellular activity, selectivity panel
   - Pharmacology: in vitro ADME, in vivo efficacy (xenograft)
   - Discussion: comparison with palbociclib/ribociclib, limitations, next steps
```

**Example 2: User asks for clinical trial paper**
```
User: "Write a paper about our Phase 2 trial results for the new immunotherapy"

Response:
1. Gather details:
   - Trial registration number
   - Number of patients, arms
   - Primary/secondary endpoints
   - Key efficacy and safety results
   - Target journal (NEJM, Lancet Oncology, JCO?)

2. Structure as clinical paper:
   - Abstract: structured with Background, Methods, Results, Conclusions
   - Introduction: disease background, unmet need, trial rationale
   - Methods: eligibility, treatment regimen, endpoints, statistics
   - Results: patient flow, baseline characteristics, efficacy, safety
   - Discussion: interpretation, comparison with other trials, limitations
   - Follow CONSORT guidelines for reporting

3. Emphasize: trial registration, IRB approval, statistical plan, adverse events
```

## Resources

### references/
- `writing_style_guide.md`: Detailed biomedical writing conventions
- `journal_formatting_specs.md`: Formatting specs for major biomedical journals
- `citation_style_guide.md`: Reference formatting for Nature, Cell, NEJM, etc.

### assets/
- `full_paper_template.pdf`: Nature/Cell paper template
- Reference these templates when discussing formatting requirements

## Important Notes

- **Always ask for clarification** on therapeutic area, drug candidate, and target journal
- **Quality over speed**: Biomedical research requires precision and reproducibility
- **Cite appropriately**: Academic integrity requires proper attribution
- **Be honest about limitations**: Acknowledge study limitations openly
- **Regulatory awareness**: Consider disclosure requirements and publication ethics
- **User provides the research content**: This skill structures and writes; the user provides the scientific data and findings
- **Safety first**: Do not provide instructions for synthesizing harmful substances; follow responsible research practices
