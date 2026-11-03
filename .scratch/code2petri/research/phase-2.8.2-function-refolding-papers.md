# Papers for Call Refolding and Exit Preservation

**Research date:** 2026-11-03

**Status:** Reading recommendations and evidence, not an approved scoring design or an implementation claim. Q3's product requirement is agreed: a simple return-or-error function remains foldable and is not Unstructured merely because it has two outcomes. Its scoring construction remains open.

**Source catalogue:** [Wil van der Aalst's publication list](https://www.vdaalst.com/publications/publications.html). Bibliographic years below follow its published editions; linked author PDFs may be earlier preprints. Page references are one-based PDF pages unless stated otherwise.

**Project context:** [Ticket 71 question tree](../specs/phase-2.8-ticket-71-question-tree.md). Tickets 71–73 were subsequently published under the approved Phase 2.8.2 breakdown; this research note does not establish a scoring construction or claim implementation.

## How these readings divide the problem

The project needs two distinct arguments: why a folded call preserves its visible normal/exception behavior, and why its retained complexity weight is justified. A behavior-preservation theorem does not by itself establish that SM is unchanged. Likewise, a numeric score does not establish that dropping an exceptional exit preserves behavior.

The readings below address component replacement, exception interfaces, substitution with multiple possible final states, the original metric, and its workflow-net assumptions. Start with the metric's definitions and the BPEL interface figures, then investigate substitution before settling Q3. This is a targeted selection from the catalogue, not an exhaustive review of its publications.

## 1. Translating Unstructured Workflow Processes to Readable BPEL: Theory and Implementation

**Authors/year:** Wil M.P. van der Aalst and Kristian Bisgaard Lassen, 2008, *Information and Software Technology* 50(3), 131–159.

**Primary text:** [Author PDF, p435](https://www.vdaalst.com/publications/p435.pdf). Listed as publication 435.

**Read:** §4, Definition 11 (PDF p.11), Definition 13 and Theorem 3 (PDF pp.13–15); §5.2 for the reduction algorithm.

**What it establishes:** Components have prescribed source/sink boundaries. Its fold operation replaces a component with a transition. Theorem 3 relates preservation of WF-net structure, safeness, and soundness to both the component and the folded net satisfying the relevant conditions. The discussion distinguishes these results from a full proof of observational equivalence, which it does not supply there. [Source](https://www.vdaalst.com/publications/p435.pdf#page=11)

**Project use, by inference:** Use the component conditions as a checklist for Ticket 73; selecting one sink and deleting another is not justified merely by calling the result Unstructured. This is also the closest theoretical companion to the project's existing SM reduction approach. It does not establish unchanged SM under outcome-merging or validate an arbitrary multi-exit-to-one-transition replacement. [Source](https://www.vdaalst.com/publications/p435.pdf#page=13)

## 2. Formal Semantics and Analysis of Control Flow in WS-BPEL

**Authors/year:** Chun Ouyang, W.M.P. van der Aalst, Stephen Breutel, Marlon Dumas, A.H.M. ter Hofstede, and H.M.W. Verbeek, 2007, *Science of Computer Programming* 67(2–3), 162–198. The author PDF identifies itself as a revised report and orders the authors differently.

**Primary text:** [Author PDF, p434](https://www.vdaalst.com/publications/p434.pdf). Listed as publication 434.

**Read:** §3.1 activity mapping and Fig.2 (PDF pp.5–6); §3.3 scopes (PDF p.10); §3.5 fault handling, particularly Figs.13–16 (PDF pp.12–14).

**What it establishes:** The paper maps structured activities and their surrounding coordination into Petri-net subnets. Its scope/fault mappings distinguish normal operation, fault occurrence, handler invocation, and propagation to a parent scope. A fault in an activity is not represented merely by treating its normal completion place as an exceptional place. [Source](https://www.vdaalst.com/publications/p434.pdf#page=12)

**Project use, by inference:** This is a concrete modeling reference for consistent normal/exception interfaces across backend and browser expansion (Ticket 72), and for an opaque call whose visible interface is richer than one ordinary transition. Its BPEL handling rules are not Python/JavaScript semantics and must be adapted rather than copied wholesale. It supplies no SM formula or proof that merging outcomes for scoring preserves SM. [Source](https://www.vdaalst.com/publications/p434.pdf#page=5)

## 3. Behavioral Service Substitution

**Authors/year:** Christian Stahl and Wil M.P. van der Aalst, 2014, in *Web Services Foundations*, 215–244.

**Primary text:** [Author PDF, p764](https://www.vdaalst.com/publications/p764.pdf). Listed as publication 764.

**Read:** §1.2.1, Definition 1 (PDF p.4); open nets and Fig.1.3 (PDF pp.5–6); §1.3.1 and Theorem 7 (PDF pp.9–11); §1.3.4 for stronger context-independent substitution requirements.

**What it establishes:** Its net model explicitly includes a set of final markings. Figure 1.3 has services with more than one permitted final state, including an error-related interaction. Open nets expose interfaces, and substitution is judged against a specified compatibility requirement and environment. The chapter distinguishes settings where the surrounding contract is known from more general compositional substitution. [Source](https://www.vdaalst.com/publications/p764.pdf#page=4)

**Project use, by inference:** A useful alternative vocabulary for Ticket 71: preserve several observable outcomes while replacing internal detail, rather than assuming every abstraction is one single-exit transition. This is service/message-passing theory, not a ready-made function-refolding algorithm. It supplies no complexity metric and does not establish unchanged SM under outcome-merging. [Source](https://www.vdaalst.com/publications/p764.pdf#page=9)

## 4. Complexity Metrics for Workflow Nets

**Authors/year:** Kristian Bisgaard Lassen and Wil M.P. van der Aalst, 2009, *Information and Software Technology* 51(3), 610–626. The author preprint is dated 2008, matching the project's existing terminology.

**Primary text:** [Author PDF, p497](https://www.vdaalst.com/publications/p497.pdf). Listed as publication 497.

**Read:** Definition 9 (PDF p.5); Definitions 16–19 (PDF pp.13–16); Definitions 21–23 (PDF pp.16–19).

**What it establishes:** The input WF-net has a single source and sink, and every node lies on a source-to-sink path. Component classification, including Unstructured, follows a separate boundary definition. The SM algorithm prioritizes recognized components, uses minimal unstructured components as its last resort, and terminates with a single weighted transition for its WF-net input. [Source](https://www.vdaalst.com/publications/p497.pdf#page=13)

**Project use, by inference:** This is the primary reference for Q3's score and Ticket 73's boundary guard. Its termination argument does not validate choosing one sink from a two-sink graph and consuming the other. A proposed function-local normalization needs a stated mapping and validation; this paper does not establish unchanged SM for that mapping. [Source](https://www.vdaalst.com/publications/p497.pdf#page=19)

## 5. Soundness of Workflow Nets: Classification, Decidability, and Analysis

**Authors/year:** W.M.P. van der Aalst, K.M. van Hee, A.H.M. ter Hofstede, N. Sidorova, H.M.W. Verbeek, M. Voorhoeve, and M.T. Wynn, 2011, *Formal Aspects of Computing* 23(3), 333–363.

**Primary text:** [Author PDF, p628](https://www.vdaalst.com/publications/p628.pdf). Listed as publication 628.

**Read:** §4, Definition 4.1 and its following discussion (PDF p.10); §5 for soundness criteria.

**What it establishes:** The formalized WF-net has one source and sink. The following discussion explicitly allows multiple start/end activities and notes that the definition can be generalized to multiple start/end places. The paper distinguishes completion and other correctness properties from mere diagram shape. [Source](https://www.vdaalst.com/publications/p628.pdf#page=10)

**Project use, by inference:** This clarifies that a one-exit restriction belongs to a selected formal model, not every possible Petri-net model. It helps specify the validation contract for reductions, but supplies neither a multi-exit SM extension nor a refolding implementation. [Source](https://www.vdaalst.com/publications/p628.pdf#page=10)

## Optional advanced background: Component-Based Software Architectures

**Full title:** *Component-Based Software Architectures: A Framework Based on Inheritance of Behavior*. W.M.P. van der Aalst, K.M. van Hee, and R.A. van der Toorn, 2002, *Science of Computer Programming* 42(2–3), 129–171.

**Primary text:** [Author PDF, p147](https://www.vdaalst.com/publications/p147.pdf). Listed as publication 147.

**Read:** §3.4, Definitions 25–26 (PDF pp.14–15), and Definition 31 (PDF p.18).

This paper separates a component's behavioral specification from its internal architecture and uses abstraction plus branching bisimulation to formulate projection inheritance. Its C-net specifications still have designated source and sink places. It is useful conceptual background for checking that a summarized call presents the expected external behavior, but it is not a general multi-exit SM solution. [Source](https://www.vdaalst.com/publications/p147.pdf#page=14)

**Important caution:** The publication list explicitly links a 2002 erratum, *Compositionality of Projection Inheritance*, publication 156, [author PDF p156](https://www.vdaalst.com/publications/p156.pdf). That PDF could not be retrieved during this research pass. Do not rely on the original paper's general compositionality theorem without obtaining and checking the correction. [Catalogue evidence](https://www.vdaalst.com/publications/publications.html)

## Immediate implications for the design interview

- Ticket 72 should aim for the same normal/exception interface whichever expansion path is used. The BPEL mapping is a modeling reference, not a substitute for the project's language-specific tests.
- Ticket 73 should validate the actual component boundary before mutation. The reproduced loss of `exception_end` is not excused by an Unstructured label.
- For Ticket 71, separate the outcome/interface abstraction from the metric derivation. A richer opaque interface or a set of allowed final states is a legitimate topic to investigate; it does not automatically define a final SM.
- Q3's product requirement is agreed; its scoring construction remains open. None of the inspected papers establishes that merging normal and exceptional exits in an analysis copy preserves the original structuredness score.

## Evidence limits

The recommendations above are based on the listed author PDFs, not only their titles or abstracts. No source code, saved graph, ticket status, or ADR was changed by this research. The optional erratum was identified from the first-party publication list but its contents were not verified. The subsequent product-requirement agreement does not imply user approval of outcome-merging, penalty rules, or new completion semantics.
