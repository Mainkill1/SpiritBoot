# Correction to historical cache-capture design prose

The normalized cache-property encoder and its frozen implementation/tests are
unchanged. Its historical `CACHE-QUERY-DESIGN.md` inherited an incorrect
investigator statement about the retained lower driver's raw validity predicate.

Before native capture implementation, the investigator found that the retained
cache-enabled and flush-capability predicates actually use the two validity bits
in IDENTIFY WORD84. Negotiated LBA48 separately uses WORD83. Comments describing
WORD83 were not evidence of the actual cache predicate. The corrected raw-capture
packet includes compiled bit-position evidence and distinguishes these facts.

No functional native capture implementation or passing native result was
produced from the incorrect statement. Keep the earlier frozen design and input
receipts as history; do not interpret their wording as a qualified raw adapter.
The current adapter must use the corrected approved packet and explicitly test
valid WORD84/invalid WORD83 and the inverse.
