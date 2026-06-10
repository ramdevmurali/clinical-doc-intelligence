# Evaluation

The evaluation harness compares golden clinical notes against expected structured outputs.

## Dataset Layout

```text
golden_set/
  notes/
  expected/
```

## Metrics

- Exact match
- Normalized match
- Entity precision
- Entity recall
- Field accuracy
- Negation accuracy
- Hallucination rate
- Source quote coverage
- Valid source span rate
- Schema valid rate
- Review rate
- Documents failed
- Average extraction latency

## Hallucination Definition

An extracted item is hallucinated when it is not present in the expected output and no source quote supports the extracted fact.

