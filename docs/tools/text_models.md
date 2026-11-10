# Local text-model adapters

`text_models` exports `IMPLEMENTATIONS`, `ANCHORS`, and `PARSERS` for Sentiment, NamedEntityRecognition, PartOfSpeechTagger, TopicModel, TextClassification, ZeroShotTextClassification, and TextSummary.

Dependencies and prerequisites are explicit: Sentiment needs `vaderSentiment`; NER/POS require a configured local spaCy model (`model_path` or `runtime_config.nlp_model`); TopicModel uses fitted local scikit-learn LDA; TextClassification loads a local joblib estimator; transformers tools require a local model and `local_files_only=True`. Missing resources raise `ToolUnavailableError`; no labels, entities, sentiment, or summaries are fabricated. Outputs are local-profile results and are not universal native-equivalence certification.
