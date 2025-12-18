# Architecture Deep Dive: The "Brain" of the Agent

## The Core Question: How Does the Agent "Think"?

Unlike traditional chatbots that generate text, this agent must produce **structured, validated data**. This document explains how we achieve that.

---

## Part 1: The "Brain" - State Machine vs. Alternatives

### Why Not a Simple Loop?

A naive approach might be:
```python
while not done:
    result = llm.generate(prompt)
    if looks_good(result):
        break
```

**Problems**:
- No way to know if you have "enough" data
- No recovery if a step fails
- No way to resume if process crashes
- Hard to debug what went wrong

### Our Solution: Explicit State Machine

The agent has 5 states, each with clear meaning:

```
IDLE → RESEARCHING → VALIDATING → COMPLETED
  ↓         ↓            ↓
FAILED ← FAILED ← FAILED
```

**State: IDLE**
- Agent is ready to start
- No active work
- Can transition to: RESEARCHING or FAILED

**State: RESEARCHING**
- Agent is executing research tasks
- Can query: "Which tasks completed? Which failed?"
- Can transition to: VALIDATING or FAILED

**State: VALIDATING**
- Agent has collected data, now validating structure
- Pydantic models enforce schema
- Can transition to: COMPLETED or FAILED

**State: COMPLETED**
- MRD successfully generated
- Can transition back to: IDLE (for next request)

**State: FAILED**
- Something went wrong
- Partial results preserved
- Can transition to: IDLE (to retry)

### How State Machine Solves "Do I Have Enough Data?"

```python
def _has_sufficient_data(self, results: Dict) -> bool:
    """Explicit check: Do we have enough to proceed?"""
    
    # 1. Check completion ratio (need 70% of tasks)
    completion_ratio = len(completed_tasks) / len(results)
    
    # 2. Check critical tasks (market analysis, regulatory)
    critical_completed = any(
        'market_analysis' in task_id or 'regulatory' in task_id
        for task_id in results.keys()
    )
    
    # 3. Return explicit boolean
    return completion_ratio >= 0.7 and critical_completed
```

**Key Insight**: Instead of the LLM "guessing" if it's done, we have **explicit rules** that can be tested and debugged.

---

## Part 2: Structured Output - From Text to Data

### The Problem with Text Output

Traditional approach:
```
LLM generates: "Triumph is successful because of TikTok marketing..."
```

**Problems**:
- Can't query: "What competitors were analyzed?"
- Can't validate: "Is this claim backed by data?"
- Can't store in database easily
- Can't use in downstream systems

### Our Solution: Pydantic Models

Every output is a **typed data structure**:

```python
class MRDOutput(BaseModel):
    competitor_analysis: List[CompetitorAnalysis]  # Not a string!
    feature_recommendations: List[FeatureRecommendation]  # Structured!
    all_claims: List[Claim]  # Every claim has sources!
```

**Example Transformation**:

**Before (Text)**:
```
"Triumph uses TikTok for marketing. Skillz has high CAC."
```

**After (Structured)**:
```json
{
  "competitor_analysis": [
    {
      "name": "Skillz",
      "weaknesses": [
        {
          "statement": "High user acquisition costs (>$50 per user)",
          "data_sources": [
            {
              "source_type": "sensor_tower",
              "source_name": "Sensor Tower Q3 2024",
              "confidence_score": 0.8,
              "timestamp": "2024-12-15T10:30:00Z"
            }
          ],
          "category": "competitor"
        }
      ]
    }
  ]
}
```

**Benefits**:
1. **Queryable**: `mrd.competitor_analysis[0].name` → "Skillz"
2. **Validatable**: Pydantic ensures structure is correct
3. **Storable**: Can save directly to database
4. **Traceable**: Every claim has source metadata

---

## Part 3: Tool Integration - How External Data Flows In

### The Challenge

We need to integrate with external tools:
- `search_sensor_tower(app_name)` → Market data
- `analyze_sentiment(social_source)` → Sentiment scores
- `check_regulatory_compliance(region)` → Legal status

**Problem**: These tools can:
- Fail (network error)
- Return empty data
- Return invalid data
- Timeout

### Our Solution: Validated Tool Boundaries

Every tool call is wrapped in validation:

```python
async def _execute_task_with_retry(self, task: ResearchTask):
    """Execute tool with retry and validation"""
    
    # 1. Call tool (with timeout)
    raw_result = await asyncio.wait_for(
        call_tool(task.required_tools[0]),
        timeout=30
    )
    
    # 2. Validate structure (Pydantic)
    validated_result = ToolOutput(**raw_result)
    
    # 3. Check data quality
    if not validated_result.has_data:
        raise InsufficientDataError()
    
    return validated_result
```

**Error Handling**:
- **Network Error**: Retry with exponential backoff
- **Empty Data**: Mark task as "insufficient data", continue
- **Invalid Data**: Raise validation error, don't proceed
- **Timeout**: Retry up to 3 times, then fail gracefully

---

## Part 4: The Research Loop - How Tasks Are Executed

### Task Execution Flow

```
Research Plan Created
    ↓
For each task in plan:
    ↓
    Check: Is circuit breaker open? → If yes, fail fast
    ↓
    Execute task (with retry logic)
    ↓
    Success? → Mark completed, store result
    Failure? → Check: Is task critical?
        ↓
        Critical (regulatory)? → Stop entire process
        Non-critical? → Log error, continue
    ↓
All tasks processed
    ↓
Check: Do we have sufficient data?
    ↓
Yes → Proceed to synthesis
No → Raise error (insufficient data)
```

### Example: Triumph Research

**Research Plan** (created by `GamblingResearchModule`):

```python
tasks = [
    ResearchTask(
        id="market_analysis_gambling",
        question="Why is Triumph succeeding where Skillz is failing?",
        required_tools=["search_sensor_tower"],
        priority=TaskPriority.CRITICAL
    ),
    ResearchTask(
        id="audience_tiktok_analysis",
        question="How are they using TikTok for acquisition?",
        required_tools=["scrape_social_media", "analyze_sentiment"],
        priority=TaskPriority.HIGH
    ),
    # ... more tasks
]
```

**Execution**:
1. Execute `market_analysis_gambling` → Success → Store result
2. Execute `audience_tiktok_analysis` → Tool timeout → Retry → Success
3. Execute `regulatory_check` → Critical → Must succeed
4. Check: 70%+ tasks completed AND critical tasks done → Proceed

---

## Part 5: Synthesis - From Research Data to MRD

### The Challenge

We have research results:
```python
{
    "market_analysis_gambling": {...},
    "audience_tiktok_analysis": {...},
    "regulatory_check": {...}
}
```

We need to create:
```python
MRDOutput(
    executive_summary="...",
    competitor_analysis=[...],
    feature_recommendations=[...],
    # ... all fields
)
```

### Our Solution: Module-Specific Synthesis

Each vertical module (`GamblingResearchModule`, `SaaSModule`) knows how to synthesize its data:

```python
async def synthesize_mrd(self, research_data: Dict) -> Dict:
    """Transform research data into MRD structure"""
    
    # 1. Extract key insights from research
    market_insights = research_data["market_analysis_gambling"]
    social_insights = research_data["audience_tiktok_analysis"]
    
    # 2. Structure into MRD format
    return {
        "executive_summary": self._create_summary(market_insights),
        "competitor_analysis": self._analyze_competitors(market_insights),
        "feature_recommendations": self._recommend_features(social_insights),
        # ... all required fields
    }
```

**Key Point**: The synthesis logic is **vertical-specific**. A SaaS module would synthesize differently than a Gambling module.

---

## Part 6: Validation - Ensuring Quality

### Three Layers of Validation

**Layer 1: Pydantic Schema Validation**
```python
# This WILL raise ValidationError if structure is wrong
mrd = MRDOutput(**mrd_draft)
```

**Layer 2: Business Rules Validation**
```python
def _validate_mrd_business_rules(self, mrd: MRDOutput):
    # Must have at least 2 competitors
    if len(mrd.competitor_analysis) < 2:
        raise ValueError("Insufficient competitor analysis")
    
    # Gambling verticals must have regulatory analysis
    if "gambling" in mrd.vertical.lower():
        if not mrd.regulatory_analysis:
            raise ValueError("Missing regulatory analysis")
```

**Layer 3: Data Quality Validation**
```python
# Check confidence scores
if mrd.confidence_score < 0.6:
    # Flag for human review
    await request_human_review(mrd)
```

---

## Part 7: Error Recovery - What Happens When Things Go Wrong

### Scenario: Sensor Tower API is Down

**What Happens**:
1. Tool call fails → Exception raised
2. Retry logic: Wait 2s, retry → Still fails
3. Wait 4s, retry → Still fails
4. Check: Is this task critical?
   - **If critical** (regulatory): Stop entire process, return error
   - **If non-critical** (gap analysis): Mark as failed, continue
5. Continue with other tasks
6. If 70%+ tasks completed: Proceed with partial data
7. Final MRD includes error context

**Result**: System doesn't crash. Partial MRD is generated with clear error messages.

---

## Summary: How the "Brain" Works

1. **State Machine**: Explicit states tell us exactly what the agent is doing
2. **Structured Data**: Pydantic models ensure output is always valid
3. **Source Tracking**: Every claim has provenance metadata
4. **Error Recovery**: Graceful degradation, not all-or-nothing
5. **Validation Gates**: Multiple layers ensure data quality

The agent doesn't "think" in the sense of generating free-form text. Instead, it:
- **Executes** a structured plan
- **Validates** at every step
- **Tracks** sources for every claim
- **Recovers** from errors gracefully

This is **structured agentic reasoning**, not "vibe coding."

