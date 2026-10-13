# Manager summary - SokoniHub listing/photo join (Week 10)

**What it does.** The system reads each listing's text and the photo's
tags, scores how well they agree (0-1), and drafts a short message for
the seller when they disagree. On the four teaching listings it flagged
1 of 4 (flag_rate 0.25, n=4 - bags 1 of 2; kitchen 0 of 1; home 0 of 1;
`rates.json`), the deliberate Nike-titled/kiondo-photo pair (NK-99),
while clearing the honest kiondo listing (KND-01). Total running cost
this week: **$0**, no API calls, no GPU.

**Risks.** (1) The sample is four fixtures, so the flag rate is a smoke
test - if we quote "25%" as a real rate we will be wrong. (2) The
word-matching encoder misses synonyms and Swahili/English mix-ups, so it
can raise a false flag; it can also miss a subtle mismatch. (3) Photos
may contain people, which is personal data under the Kenya Data
Protection Act 2019. (4) "Generation" here is a labelled stub, and it
would be easy for a reader to mistake it for a real product photo.

**Mitigations.** Every rate ships with its denominator; the encoder is
pinned by source hash and cross-checked with a real local CLIP run
(`encoder_pin.json`, `evidence/clip_crosscheck.log`); person/face/child
tags trigger a privacy flag before anything is published; a human
moderator reviews every flagged listing before a seller sees a message;
generated pixels are watermarked in-file and JSON-labelled
`not_a_photo_of_the_sku: true`, kept out of `gold/`.

**What we will not claim.** We do not claim this detects counterfeits,
fraud, or "fake" sellers - NK-99 shows *photo and title disagreement*
only. We do not claim accuracy percentages from n=4, do not claim the
CLIP cross-check tuned the threshold, and do not claim any generated
image is a photo of the SKU. No listing is auto-edited, auto-removed, or
auto-published by this system.

**Next step.** Agree the human review owner and the wording of the
seller message, then re-run on a real (consented) photo slice before any
rate is quoted outside this room.
