---
title:  Beamer Slides
author:
    - Awesome Author
    - Another Awesome Author
institute: '\protect{\large Some Random Place}'
date: \today
bibliography: ./bibliography.bib
link-citations: true
template: beamer
csl: ieee
---

<!-- For newline between authors or any other lines between multiple authors set
authorsep in yaml header like so:

authorsep: '\protect{\\}'

To change the font, set like this. In fact any latex commands can be inserted
using a literal string '' and \protect. The Default template will set a small
institution font. The following changes it to large.

institute: '\protect{\large Some Random Place}'

Above inserts a single newline between authors. -->

# Section 1

## Slide 1

- This is a test
- A citation can be included like this. [@einstein1905elektrodynamik].
- Another

## Slide 3

- This is some more test
- A citation of a book [@darwin1871descent]
- Adding a footnote ^[footnote] is simple.


# Section 2

## Section 2 Slide 1

- Does this pause?

. . .

- Yes!

## Section 2 Slide 3
  * And this?
* But this also?
* A misc citation. [@pandoc]

. . .

### And this?
  * And this?

# References
## References {.allowframebreaks}


