# Graph-RAG System Plan for NutritionFacts.org Data

## Dataset Overview

The dataset contains crawled content from NutritionFacts.org, organized by health/nutrition topics.

### Folder Structure

```
data/nutritionfacts.org/
└── topics/
    ├── A/
    │   ├── a2-milk/
    │   │   └── does-a2-milk-carry-less-autism-risk/
    │   │       ├── metadata.json
    │   │       ├── transcript.txt
    │   │       └── video.mp4
    │   ├── abdominal-fat/
    │   │   └── do-chia-seeds-help-with-belly-fat/
    │   │       ├── metadata.json
    │   │       └── transcript.txt
    │   └── ...
    ├── B/
    ├── C/
    └── ... (A-Z)
```

### Hierarchy

- **Topics** organized alphabetically (A-Z folders)
- Each **topic** contains multiple **video slugs**
- Each **video folder** contains:
  - `metadata.json` — structured metadata
  - `transcript.txt` — video transcript
  - `video.mp4` — (optional) video file

### Example metadata.json

```json
{
  "url": "https://nutritionfacts.org/video/do-chia-seeds-help-with-belly-fat/",
  "youtube_url": null,
  "vimeo_url": "https://vimeo.com/262773037",
  "vimeo_url_embedded": "https://player.vimeo.com/video/262773037?badge=0&autopause=0&player_id=0&app_id=58479",
  "title": "Do Chia Seeds Help with Belly Fat?",
  "description": "The secret to unlocking the benefits of chia seeds may be grinding them up.",
  "author": "Michael Greger M.D. FACLM",
  "date": "June 29, 2018",
  "volume": "Volume 42",
  "doctors_note": "The video I referred to is Which Are Better: Chia Seeds or Flaxseeds?.\nFor more on flax, check out:\nFlaxseeds for Hypertension\nFlaxseeds and Breast Cancer Survival...",
  "sources_cited": [
    {
      "text": "Marcinek K, Krejpcio Z. Chia seeds (Salvia hispanica): health promoting properties and therapeutic applications – a review. Rocz Panstw Zakl Hig. 2017;68(2):123-129.",
      "url": "https://www.ncbi.nlm.nih.gov/pubmed/28646829"
    },
    {
      "text": "Nieman DC, Cayea EJ, Austin MD, et al. Chia seed does not promote weight loss or alter disease risk factors in overweight adults. Nutr Res. 2009;29(6):414-8.",
      "url": "https://www.ncbi.nlm.nih.gov/pubmed/19628108"
    }
  ],
  "topics": [
    "abdominal fat",
    "chia seeds",
    "cholesterol",
    "fiber",
    "inflammation",
    "omega-3 fatty acids",
    "weight loss"
  ]
}
```

---

## Why Graph-RAG?

### The Problem with Vector Search Alone

Vector search finds documents that are **semantically similar** to the query. It misses documents that are **domain-related but don't sound similar**.

### Example

Query: *"How do I lower cholesterol?"*

| Method | Finds | Misses |
|--------|-------|--------|
| Vector search | Chunks containing "cholesterol", "LDL", "lower cholesterol" | Chunks about "soluble fiber", "bile acids", "oat beta-glucan" |
| Graph + Ontology | All of the above | Nothing — ontology knows the biological relationships |

### The Ontology Advantage

An ontology encodes domain-expert knowledge:

```
Soluble fiber → binds → Bile acids → forces liver to use → Cholesterol → lowers → Serum LDL
```

Graph traversal finds fiber/bile acid chunks for a cholesterol query — **because the ontology encodes relationships that embeddings don't capture**.

---

## Critical Insights from Practitioners

> Based on analysis of the Maven "Systematically Improve RAG Applications" course transcripts.

### 1. Re-ranking is a Hack — Fix Retrieval Instead

> "Re-ranking is purely a hack of our underlying retrieval sucks... If the underlying retrieval actually worked, you wouldn't have to re-rank. Re-ranking only applies to <1% of your data." — Daniel Svonava

**Action**: Push signals INTO the embedding/indexing phase. Don't rely on re-ranking to fix poor retrieval.

### 2. Text Embeddings Don't Understand Numbers

> "Text embedding models understand numbers through how those co-occur in training data... there is no underlying concept of 49 is one less than 50 in the latent space." — Daniel Svonava

**Action**: Use **specialized encoders** for non-text data:
- Numerical encoder for dosages, study sizes, publication years
- Temporal encoder for dates
- Categorical encoder for food types, conditions
- Graph encoder for ontology relationships

### 3. Filters Are Overused — Use Smooth Biases

> "If you model biases with filters, you are using a very crude step function to approximate a smooth preference." — Daniel Svonava

**Action**: Replace hard filters with smooth biases in the vector space. A 2017 video shouldn't be excluded — just weighted lower than 2024.

### 4. Graph as INPUT to Embeddings, Not Just Query-Time Traversal

> "From our point of view, graphs are just users clicking on things making implicit links... graph is the input to embeddings." — Daniel Svonava

**Action**: Pre-encode ontology relationships INTO the embeddings at index time, not just traverse at query time.

### 5. Evaluate for False Negatives AND Sufficiency

> "You want to know not only which retrieved docs were relevant, but also: the documents I didn't retrieve, were any of those relevant?" — Skylar Payne

**Action**: Build evals that check:
- False negatives: relevant chunks outside top-k
- Sufficiency: can the query be answered with retrieved context?

### 6. Sub-Agents for Context-Expensive Operations

> "All the exploration when refining queries eats up context window. But because it's a sub-agent, once it finds the right snippets, you can throw away that context." — Beyang Liu

**Action**: Use sub-agents for entity extraction and graph traversal to preserve main agent context.

### 7. Biggest Anti-Pattern: Complexity Without Evals

> "90+ percent of the time the new system did worse after you evaluated it." — Skylar Payne

**Action**: Establish baseline with simple vector search FIRST. Add components one at a time with evals.

### 8. Tool Overload Confuses Models

> "Naively throwing in all the tools that an MCP server defines is a great recipe for confusing the model." — Beyang Liu

**Action**: Curate a minimal tool set. Don't expose every retrieval method as a tool.

### 9. Look at Your Data at Every Step

> "It's not sufficient to just look at the inputs and outputs when you have a complex system. The problems might be somewhere in the middle." — Skylar Payne

**Action**: Log and inspect intermediate outputs: chunks, entities, graph traversal paths, re-ranked results.

### 10. Chunking: Don't Over-Optimize, Don't Under-Size

> "Most people that implement RAG start with chunking because they copy and pasted some tutorial... the smaller the chunk, the less meaning it has." — Skylar Payne

**Action**: Use long context models. Chunk by semantic boundaries. Test chunking strategies with synthetic questions generated BEFORE chunking.

---

## Indexing Strategy (Revised)

| Data Field | Index Method | Encoder Type | Purpose |
|------------|--------------|--------------|---------|
| **Transcripts** | Vector | Text embedding (fine-tuned) | Semantic similarity |
| **Transcripts** | Lexical (BM25) | N/A | Exact terms, scientific names |
| **Transcripts** | Graph embedding | Graph encoder | Entity relationships from ontology |
| **Title** | Vector + Lexical | Text embedding | Match video by name |
| **Description** | Vector | Text embedding | Quick relevance via summary |
| **Topics** | Categorical bias | Categorical encoder | Smooth topic weighting (not hard filter) |
| **Sources Cited** | Graph nodes | Graph encoder | Videos sharing evidence |
| **Doctor's Note** | Vector + Link extraction | Text embedding | Additional context + video relationships |
| **Date/Volume** | Temporal bias | Temporal encoder | Recency weighting (not hard filter) |

### Key Change: Encoder Stacking (Mixture of Encoders)

Instead of a single text embedding, create a **composite embedding** that combines:

```
Final Embedding = aggregate(
    text_encoder(transcript),
    graph_encoder(entity_relationships),
    temporal_encoder(publication_date),
    categorical_encoder(topics),
    numerical_encoder(study_metrics)
)
```

This allows the embedding to capture signals that text embeddings miss.

---

## Graph Components

### What To Build

| Component | Description | Priority |
|-----------|-------------|----------|
| Entity Extraction | NER on transcripts: foods, conditions, nutrients, mechanisms | P0 |
| Ontology | Nutrition/biomedical relationships (MeSH, custom) | P0 |
| Graph Embeddings | Pre-encode ontology into embeddings at index time | P1 |
| Graph Index | `(Chunk)-[:MENTIONS]->(Entity)` for query-time expansion | P1 |
| Retrieval Pipeline | Hybrid search + graph-augmented embeddings | P2 |

### Graph Schema

```
(Chunk)-[:MENTIONS]->(Entity)
(Entity)-[:RELATION]->(Entity)          # from ontology (e.g., produces, inhibits, causes)

(Video)-[:HAS_TOPIC]->(Topic)
(Video)-[:CITES]->(Source)
(Video)-[:RELATED_TO]->(Video)          # from doctor's notes links
(Topic)-[:RELATED_TO]->(Topic)          # co-occurrence
```

### Example Entity Relationships (Ontology)

```
(Fiber)-[:FERMENTED_BY]->(Gut Bacteria)
(Gut Bacteria)-[:PRODUCES]->(Butyrate)
(Butyrate)-[:REDUCES]->(Inflammation)

(Omega-3)-[:INHIBITS]->(Arachidonic Acid)
(Arachidonic Acid)-[:PRECURSOR_OF]->(Prostaglandins)
(Prostaglandins)-[:CAUSE]->(Inflammation)

(Saturated Fat)-[:INCREASES]->(LDL Cholesterol)
(LDL Cholesterol)-[:CAUSES]->(Atherosclerosis)
(Atherosclerosis)-[:LEADS_TO]->(Heart Disease)
```

---

## Retrieval Pipeline (Revised)

### Architecture: Sub-Agent Based

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│  MAIN AGENT                         │
│  - Receives query                   │
│  - Orchestrates sub-agents          │
│  - Generates final answer           │
└─────────────────────────────────────┘
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│ RETRIEVAL│    │ ENTITY       │    │ GRAPH        │
│ SUB-AGENT│    │ SUB-AGENT    │    │ SUB-AGENT    │
│          │    │              │    │              │
│ - Vector │    │ - Extract    │    │ - Traverse   │
│ - BM25   │    │   entities   │    │   ontology   │
│ - Merge  │    │ - Link to    │    │ - Find       │
│          │    │   ontology   │    │   related    │
└──────────┘    └──────────────┘    └──────────────┘
    │                  │                  │
    └──────────────────┴──────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ COMBINE & RANK  │
              │ - Deduplicate   │
              │ - Score by      │
              │   multiple      │
              │   signals       │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ VERIFICATION    │
              │ SUB-AGENT       │
              │ - Check chunks  │
              │   support answer│
              │ - Request more  │
              │   if needed     │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ LLM GENERATION  │
              │ - Generate      │
              │   answer with   │
              │   citations     │
              │ - Validate      │
              │   citations     │
              └─────────────────┘
```

### Why Sub-Agents?

1. **Context preservation**: Entity extraction and graph traversal consume tokens. Sub-agents discard their exploration context after returning results.
2. **Specialization**: Each sub-agent can use optimal prompts/models for its task.
3. **Parallelization**: Retrieval, entity extraction, and graph traversal can run concurrently.

---

## Implementation Steps (Revised)

### Phase 0: Establish Baseline (CRITICAL)

1. **Simple vector search baseline**
   - Chunk transcripts (~500 tokens, semantic boundaries)
   - Embed with off-the-shelf model (e.g., text-embedding-3-large)
   - Index in vector store
   - Measure retrieval quality with synthetic questions

2. **Create evaluation dataset**
   - Generate synthetic questions from transcripts BEFORE chunking
   - Include questions requiring multi-hop reasoning
   - Annotate with ground truth chunks

3. **Define metrics**
   - Recall@k (are relevant chunks in top-k?)
   - False negative rate (relevant chunks outside top-k?)
   - Sufficiency (can query be answered with retrieved chunks?)
   - End-to-end answer quality

### Phase 1: Add Lexical Search

1. **Index chunks in BM25**
2. **Hybrid retrieval**: Vector + BM25
3. **Measure improvement over baseline**
4. **Only proceed if metrics improve**

### Phase 2: Entity Extraction + Ontology

1. **Build/acquire ontology**
   - Start with MeSH for medical vocabulary
   - Add custom nutrition relationships
   - Validate coverage against transcript entities

2. **Extract entities from transcripts**
   - Use biomedical NER (scispaCy, PubMedBERT)
   - Link to ontology nodes
   - Store `(Chunk)-[:MENTIONS]->(Entity)` relationships

3. **Measure entity extraction quality**
   - Precision/recall on sample of transcripts
   - Coverage of query-relevant entities

### Phase 3: Graph Embeddings

1. **Train graph embeddings on ontology**
   - Use node2vec, TransE, or similar
   - Capture `(Entity)-[:RELATION]->(Entity)` semantics

2. **Create composite embeddings**
   - Aggregate text + graph embeddings per chunk
   - Use encoder stacking approach

3. **Re-index with composite embeddings**
4. **Measure improvement over Phase 1**

### Phase 4: Query-Time Graph Expansion

1. **Build graph traversal sub-agent**
   - Extract entities from query
   - Traverse ontology 1-2 hops
   - Retrieve chunks mentioning related entities

2. **Integrate with retrieval pipeline**
3. **Measure improvement over Phase 3**

### Phase 5: Verification & Feedback Loops

1. **Add verification sub-agent**
   - Check if retrieved chunks support generated answer
   - Request additional retrieval if insufficient

2. **Add citation validation**
   - Force inline citations
   - Validate each citation exists
   - Semantic validation that citation supports claim

---

## Tool Design (Minimal Set)

Avoid tool overload. Expose only essential tools to the main agent:

| Tool | Purpose | Implementation |
|------|---------|----------------|
| `search_videos` | Semantic + lexical search over transcripts | Vector + BM25 hybrid |
| `find_related` | Find videos related by topic/source | Graph traversal |
| `get_video_details` | Fetch metadata for a video | Direct lookup |
| `search_sources` | Search cited research papers | Source graph + text search |

Sub-agents have access to lower-level tools:
- `extract_entities` — NER on text
- `traverse_ontology` — Graph hop operations
- `embed_query` — Get query embedding for debugging

---

## Ontology Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **MeSH** | Comprehensive medical vocabulary, hierarchical | May need mapping to nutrition terms | Use as base |
| **FoodOn** | Food-focused ontology | Less coverage of health conditions | Supplement MeSH |
| **Custom** | Tailored to NutritionFacts content | Requires manual curation | Add domain-specific relations |
| **Hybrid** | Best coverage | Integration complexity | Recommended approach |

### Recommended Approach

1. Start with MeSH for conditions, symptoms, biological processes
2. Add FoodOn for food entities
3. Create custom relations specific to NutritionFacts:
   - `(Food)-[:MAY_HELP]->(Condition)`
   - `(Food)-[:CONTAINS]->(Nutrient)`
   - `(Study)-[:SHOWS]->(Effect)`

---

## Evaluation Framework

### Retrieval Metrics

| Metric | What It Measures | Target |
|--------|------------------|--------|
| Recall@10 | Relevant chunks in top 10 | >80% |
| Recall@50 | Relevant chunks in top 50 | >95% |
| False Negative Rate | Relevant chunks missed entirely | <5% |
| Sufficiency Rate | Queries answerable with retrieved chunks | >90% |

### End-to-End Metrics

| Metric | What It Measures | Target |
|--------|------------------|--------|
| Answer Correctness | Factual accuracy vs. ground truth | >85% |
| Citation Accuracy | Citations support claims | >95% |
| Hallucination Rate | Claims not supported by sources | <5% |

### Evaluation Process

1. **Per-phase evaluation**: Measure after each implementation phase
2. **Regression testing**: Ensure new features don't break existing quality
3. **Segment analysis**: Check performance by query type (simple lookup, multi-hop reasoning, temporal)
4. **False negative analysis**: Manually review missed relevant chunks

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What To Do Instead |
|--------------|--------------|---------------------|
| Chunking too small | Dilutes meaning, increases noise | Use long context, semantic boundaries |
| Keeping bad chunks | Footers, duplicates crowd out relevance | Inspect shortest chunks, deduplicate |
| Hard metadata filters | Excludes potentially relevant results | Use smooth biases in embedding space |
| Over-relying on re-ranking | Only fixes <1% of data, masks retrieval issues | Fix retrieval quality directly |
| Stringifying numbers | Text embeddings don't understand numerical values | Use specialized encoders |
| Adding complexity without evals | 90%+ chance new system is worse | Baseline first, measure each change |
| Tool overload | Confuses the model | Curate minimal tool set |
| Ignoring false negatives | Miss improvement opportunities | Evaluate beyond top-k |
| Silent failures | Encoding errors, parsing failures drop documents | Monitor counts at each pipeline stage |

---

## Summary

The Graph-RAG system combines:

- **Vector search** — finds semantically similar content
- **Lexical search** — finds exact matches
- **Graph-augmented embeddings** — encodes ontology relationships into vector space
- **Query-time graph expansion** — finds domain-related content via sub-agents

### Key Differentiators from Standard RAG

1. **Encoder stacking**: Combine text, graph, temporal, categorical encoders
2. **Sub-agent architecture**: Preserve context, enable specialization
3. **Smooth biases over hard filters**: Better ranking, fewer false negatives
4. **Ontology as embedding input**: Not just query-time traversal
5. **Verification feedback loop**: Check sufficiency before generation

### Success Criteria

- Retrieve content that vector search alone misses (e.g., fiber for cholesterol query)
- Answer multi-hop reasoning questions
- Maintain high precision while improving recall
- Generate answers with validated citations

---

## Implementation Progress

### Phase 0-1: Baseline Implementation (Completed 2025-12-13)

#### What Was Built

1. **NutritionFacts Data Loader** (`data/nutritionfacts.org/loader.py`)
   - Loads 112 video documents from `data/nutritionfacts.org/topics/`
   - Extracts: doc_id, title, content (transcript), description, date, topics, sources_cited, doctors_note
   - Includes comprehensive unit tests (26 tests passing)

2. **Manual Verification Script** (`data/nutritionfacts.org/verify_search.py`)
   - Loads documents and chunks them (500 chars, 50 overlap)
   - Generates embeddings via LM Studio (text-embedding-bge-large-en-v1.5)
   - Indexes into embedded Weaviate
   - Supports vector, BM25, and hybrid search modes
   - Interactive query mode for testing

#### Dataset Statistics

- **Documents**: 112 videos
- **Chunks**: 1,624 (after chunking at 500 chars with 50 overlap)
- **Embedding Time**: ~24 seconds for all chunks
- **Embedding Model**: text-embedding-bge-large-en-v1.5 (1024 dimensions)

#### Search Quality Results (Hybrid Mode, alpha=0.5)

**Manual Test Queries:**

| Query | Top Result | Score | Quality |
|-------|------------|-------|---------|
| "How do I lower cholesterol?" | Low-Carb Diets and Coronary Blood Flow | 0.70 | Good |
| "What are the benefits of chia seeds?" | Do Chia Seeds Help with Belly Fat? | 0.94 | Excellent |
| "Best way to cook sweet potatoes?" | The Best Way to Cook Sweet Potatoes | 1.00 | Perfect |
| "How does fiber affect gut health?" | A2 Milk / Autism (gut mention) | 0.50 | Needs improvement |
| "What causes inflammation?" | Dietary Cholesterol and Inflammation | 0.69 | Good |
| "What foods help with weight loss?" | Apple Cider Vinegar Weight Loss | 0.84 | Excellent |
| "Is acrylamide dangerous?" | How Not To Age (acrylamide section) | 0.89 | Excellent |
| "What are the health benefits of omega-3?" | Chia Seeds (omega-3 content) | 0.67 | Good |

**QA Pair Evaluation (64 questions generated by qwen2.5-7b-instruct-mlx):**

| Metric | Value |
|--------|-------|
| Hit Rate@10 | 98.44% (63/64) |
| MRR (Mean Reciprocal Rank) | 0.79 |

The one miss was for a question about "physicians in the 1950s" where the expected video "dont-wait-until-your-doctor-kicks-the-habit" was not in the top 10 results.

Run evaluation: `uv run python data/nutritionfacts.org/eval_qa.py`

#### Observations

**Strengths:**
- Direct matches work extremely well (sweet potatoes, chia seeds, acrylamide)
- Hybrid search balances semantic and lexical matching
- Metadata (topics, title) enriches results

**Weaknesses (Need Graph-RAG):**
- "How does fiber affect gut health?" misses butyrate/microbiome content
- Indirect relationships not captured (fiber → bile acids → cholesterol)
- Multi-hop reasoning queries underperform

#### Files Created

```
data/nutritionfacts.org/
├── loader.py                    # Document loader with metadata extraction
├── verify_search.py             # Manual verification script
├── eval_qa.py                   # QA pair evaluation script
├── qa/                          # Generated QA pairs
│   └── qwen2.5-7b-instruct-mlx/ # QA pairs by model
│       └── *.json               # Individual QA files
└── topics/                      # 112 video folders (existing)
    └── A/topic/video/
        ├── metadata.json
        └── transcript.txt

tests/unit/data/
├── __init__.py
└── test_nutritionfacts_loader.py  # 26 unit tests
```

#### Prerequisites

- **LM Studio** running locally with `text-embedding-bge-large-en-v1.5` model loaded
- Model serves at `http://localhost:1234/v1`
- First embedding call may take ~30s while model loads
- Use `--hash-based` flag to run without LM Studio (for testing)

#### Usage

```bash
# Test loader
uv run python data/nutritionfacts.org/loader.py

# Run verification (requires LM Studio with bge-large model)
uv run python data/nutritionfacts.org/verify_search.py --top-k 5

# Run with hash-based embeddings (no network)
uv run python data/nutritionfacts.org/verify_search.py --hash-based

# Interactive mode
uv run python data/nutritionfacts.org/verify_search.py --interactive

# Run QA evaluation (auto-discovers all QA pairs in qa/ directory)
uv run python data/nutritionfacts.org/eval_qa.py

# QA eval with different modes
uv run python data/nutritionfacts.org/eval_qa.py --mode vector   # Vector only
uv run python data/nutritionfacts.org/eval_qa.py --mode bm25     # BM25 only
uv run python data/nutritionfacts.org/eval_qa.py --mode hybrid   # Hybrid (default)
```

#### Next Steps (Phase 2+)

1. **Generate QA Pairs**: Create synthetic questions from chunks for eval dataset
2. **Build Entity Extractor**: NER on transcripts for foods, conditions, nutrients
3. **Create Nutrition Ontology**: Map relationships (fiber→bile acids→cholesterol)
4. **Graph Embeddings**: Encode ontology relationships into vector space
5. **Query-Time Graph Expansion**: Find related content via ontology traversal

---

## References

Insights derived from Maven "Systematically Improve RAG Applications" course:

- Skylar Payne — RAG Anti-patterns in the Wild, and How to Fix Them
- Daniel Svonava — Natural Language Search on Semi-Structured Data
- Beyang Liu — Rethinking RAG from First Principles for Agents
- Jason Liu — Course lectures on evaluation, segmentation, routing
- Ayush Chaurasia — Improving Retrievers by Reranking and Embedding Fine-tuning
- Adit Abraham — Better RAG Through Better Data
