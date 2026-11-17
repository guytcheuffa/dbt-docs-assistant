# Génération : résultats sur 90 questions

Réponses : `qwen-flash` (consigne v1) ; recherche `hybrid_rerank`, 5 passages ; juge : `qwen3.8-flash`. Tokens consommés au total : 953148.

## Refus

- Refus correct sur les questions sans réponse : 12/12 (100%)
- Refus à tort sur les questions avec réponse : 1/78 (1%)
  - dont page attendue absente du contexte (faute de la recherche) : 0

## Réponses données (77 questions avec réponse, non refusées)

- Au moins une citation : 77/77 (100%)
- Page attendue citée : 66/77 (86%)
- Fidélité aux passages (juge) : oui 72, partielle 5, non 0
- Justesse vs référence (juge) : oui 63, partielle 12, non 2

## À relire

- q008 fidélité=yes justesse=partial : How do I give a default value to env_var?
- q016 fidélité=yes justesse=partial : What information does the target variable give access to?
- q026 fidélité=yes justesse=partial : What does the manifest.json artifact contain?
- q032 fidélité=yes justesse=partial : How do I configure the microbatch incremental strategy?
- q033 fidélité=yes justesse=partial : How do I create a snapshot?
- q038 fidélité=yes justesse=partial : How do I define YAML selectors?
- q047 fidélité=yes justesse=partial : How do I use environment variables in my project?
- q055 fidélité=yes justesse=partial : What is the difference between dbt run and dbt build?
- q056 fidélité=partial justesse=yes : What is the difference between source() and ref()?
- q057 fidélité=partial justesse=yes : What is the difference between a seed and a source?
- q058 fidélité=yes justesse=partial : What incremental strategies are available and how do merge and delete+insert differ?
- q060 fidélité=partial justesse=yes : What is the difference between singular and generic tests?
- q066 fidélité=yes justesse=partial : How do I version a model and keep a stable contract for consumers?
- q067 fidélité=yes justesse=partial : How do I control access to a model and reference a model from another project?
- q068 fidélité=yes justesse=partial : How do I pass variables on the command line and read them in a model?
- q069 fidélité=partial justesse=no : How do I document a column and have the description stored in the warehouse?
- q072 fidélité=yes justesse=no : How can I limit the amount of data processed in development?
- q078 fidélité=partial justesse=yes : I have a small static list of country codes. Should I load it as a seed or a source?
- q062 (refus à tort, page attendue dans le contexte : True) : What is the difference between state:modified and state:new?
