---
title:  Example Article
author: Awesome Author
date: \today
bibliography: ./bibliography.bib
link-citations: true
# csl: ieee
abstract: >
    A description of simple article generation with `pndconf`. We give the example
    configurations that generates this article.

references:
- author:
  - family: Person
    given: Some
  container-title: Yaml Citation
  event-place: Some Awesome Venue
  id: yaml2020citation
  issued: 2020-06
  title: Yaml Citation
  type: article-journal
---

# Introduction

`pndconf` is fairly simple to use. Let's say your templates and csl files are in
the same directory as the article **and** you want to output to PDF. Then you
simply need to run `pndconf`. It'll pick up any templates given either on the
command line or in the yaml metadata and output the required document.

# Abstract and Bibliography

Abstract can be inserted via yaml as in metadata above. Of course it only makes
sense to write an abstract for an article.

See the example metadata above for a simple use case. References can be included
in a bib file as given in `bibliography` key above. They can also be included in
yaml format

To cite something simply use [@darwin1871descent]. This should cite from
`bibliography.bib`. We can also cite from the yaml references as
[@yaml2020citation]. The two can be combined easily.

You only need to insert a "References" heading at the end and the references
will be generated below that.

# Formatting

Standard markdown formatting is supported and additional `pandoc` extensions can
be added easily.

# Pandoc options

All standard `pandoc` formatting options can be passed to pandoc. See
<https://pandoc.org/MANUAL.html> for more details. Notable are markdown specific
options and the output specific options.

For example in pandoc a footnote can be added like: ^[This is a footnote].

# References
