# Génération : résultats sur 90 questions

Réponses : `qwen3.8-flash` (consigne v1) ; recherche `hybrid_rerank`, 5 passages ; juge : `qwen3.8-flash`. Tokens consommés au total : 795109.

## Refus

- Refus correct sur les questions sans réponse : 12/12 (100%)
- Refus à tort sur les questions avec réponse : 2/78 (3%)
  - dont page attendue absente du contexte (faute de la recherche) : 0

## Réponses données (76 questions avec réponse, non refusées)

- Au moins une citation : 76/76 (100%)
- Page attendue citée : 68/76 (89%)
- Fidélité aux passages (juge) : oui 76, partielle 0, non 0
- Justesse vs référence (juge) : oui 56, partielle 19, non 1

## À relire

- q008 fidélité=yes justesse=partial : How do I give a default value to env_var?
- q016 fidélité=yes justesse=partial : What information does the target variable give access to?
- q026 fidélité=yes justesse=partial : What does the manifest.json artifact contain?
- q033 fidélité=yes justesse=partial : How do I create a snapshot?
- q038 fidélité=yes justesse=partial : How do I define YAML selectors?
- q041 fidélité=yes justesse=partial : How do I write and use a macro?
- q047 fidélité=yes justesse=partial : How do I use environment variables in my project?
- q048 fidélité=yes justesse=partial : How do I set up a CI job?
- q051 fidélité=yes justesse=partial : How do I set a custom alias for a model?
- q053 fidélité=yes justesse=partial : What is the difference between a view and a table materialization?
- q055 fidélité=yes justesse=partial : What is the difference between dbt run and dbt build?
- q056 fidélité=yes justesse=partial : What is the difference between source() and ref()?
- q057 fidélité=yes justesse=partial : What is the difference between a seed and a source?
- q058 fidélité=yes justesse=partial : What incremental strategies are available and how do merge and delete+insert differ?
- q066 fidélité=yes justesse=partial : How do I version a model and keep a stable contract for consumers?
- q067 fidélité=yes justesse=partial : How do I control access to a model and reference a model from another project?
- q068 fidélité=yes justesse=partial : How do I pass variables on the command line and read them in a model?
- q072 fidélité=yes justesse=no : How can I limit the amount of data processed in development?
- q074 fidélité=yes justesse=partial : Why does dbt put my tables in a schema like dbt_alice_marketing instead of just marketing?
- q077 fidélité=yes justesse=partial : How can I see the SQL that dbt generates for a model without running it?
- q062 (refus à tort, page attendue dans le contexte : True) : What is the difference between state:modified and state:new?
- q069 (refus à tort, page attendue dans le contexte : True) : How do I document a column and have the description stored in the warehouse?
