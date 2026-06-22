# TMSS OmniMark Script Packages

This note records the legacy TMSS / JCALS script packages found in the public A-10 Technical Order Engineering Support solicitation package. They are documented here because they belong to the same broader technical data ecosystem as C4/JEDMICS conversion: old military technical order data, SGML/XML publishing pipelines, composed PDF or PostScript output, and repository or PLM delivery rules.

These files are **not aircraft operational software**, **not A-10 OFP software**, and **not Patriot software**. They are technical manual publishing automation scripts.

## Why this matters to this converter

The C4/PDF converter handles legacy raster drawing data. The A-10 package shows a nearby legacy publishing workflow where SGML technical order instances were processed through TMSS tools, OmniMark programs, FOSI composition, and DLComposer output. That gives useful context for future conversion work around technical data packages that may contain a mixture of raster drawings, SGML/XML manuals, script packages, and composed PDF or PostScript output.

The same A-10 PLM data exchange material also listed `.c4` as an accepted Teamcenter dataset file type, so this package is useful evidence that C4 appears in Air Force technical data exchange workflows.

## Packages observed

Six script ZIP entries appeared in the solicitation package, but they reduce to three unique script packages.

| Package | Duplicate entries | Contents | Purpose |
| --- | ---: | --- | --- |
| `38784STD-BV8a_scripts.zip` | 4 copies | 20 `.xom`, 15 `.sh`, 8 `.txt` | MIL-STD-38784 style technical manual automation |
| `7700H-CV9D0P0_scripts.zip` | 1 copy | 4 `.xom`, 6 `.sh` | MIL-DTL-7700 flight manual / checklist processing |
| `9977L-GV9D0P0_scripts.zip` | 1 copy | 2 `.xom`, 1 `.sh`, 1 `.txt` | MIL-DTL-9977 Appendix G style multiple carriage number processing |

## File types found

| Extension | Meaning in this context |
| --- | --- |
| `.xom` | OmniMark transformation program source files |
| `.sh` | Unix shell wrapper scripts that call OmniMark and DLComposer |
| `.txt` | Readme and instruction notes |
| `.sgml` / `.sgm` | SGML technical order instances and generated SGML output |
| `.ps` | PostScript output from composition |
| `.out` | Intermediate OmniMark output |
| `.inputs` | Intermediate composition input lists |
| `.acrm` | Generated acronym list intermediate/output file |
| `.dat` | Data input/output file, such as verification status matter |

## Common tools and paths

The shell scripts are wrappers around a legacy TMSS / JCALS publishing environment. They refer to tools and paths such as:

```text
omnimark
DLcomposer
LM_LICENSE_FILE=$OMNIMARK_DIR/license.dat
/jcals/wss_data/sgml_applications/services/omniprograms/
/jcals/wss_data/sgml_applications/services/library/28001con.syn
/jcals/wss_data/sgml_applications/services/library/wndlibrary.txt
/jcals/wss_data/sgml_applications/FOSIs/
```

That means the scripts expected OmniMark, DLComposer, FOSI files, SGML libraries, and a JCALS/TMSS directory layout to already exist.

## `38784STD-BV8a_scripts.zip`

This is the largest script set. It supports MIL-STD-38784 style technical manuals, including illustrated parts breakdown and front/back matter automation.

### File inventory

```text
38784STD-BV3_acronymlist1.xom
38784STD-BV3_normal_moti.xom
38784STD-BV3_verstat.xom
38784STD-BV4_sssn2.xom
38784STD-BV5_volpages_lep1.xom
38784STD-BV5_volume_lep1.xom
38784STD-BV8_acronymlist2.xom
38784STD-BV8_alphabetical_index.xom
38784STD-BV8_combine_table.xom
38784STD-BV8_num_index1.xom
38784STD-BV8_num_index2.xom
38784STD-BV8_primary_index.xom
38784STD-BV8_refdes1.xom
38784STD-BV8_refdes2.xom
38784STD-BV8_refdes_sssn1.xom
38784STD-BV8_replace_verstat.xom
38784STD-BV8_secondary_index.xom
38784STD-BV8_sssn1.xom
38784STD-BV8_table.xom
38784STD-BV8_volume_lep2.xom
38784STD-BV3_moti.sh
38784STD-BV8_acronym.sh
38784STD-BV8_generate_index.sh
38784STD-BV8_generate_table.sh
38784STD-BV8_index.sh
38784STD-BV8_lep.sh
38784STD-BV8_num_index.sh
38784STD-BV8_refdes.sh
38784STD-BV8_refdes_sssn.sh
38784STD-BV8_sssn.sh
38784STD-BV8_verstat.sh
38784STD-BV8_volpages_lep.sh
38784STD-BV8_volumes_lep.sh
38784STD-BV8_volumes_volpages_lep.sh
38784STD-BV8a_generate_index_after_change.sh
38784STD-BV3_moti_readme.txt
38784STD-BV8_numindx_readme.txt
38784STD-BV8_refdes_readme.txt
38784STD-BV8_tables_readme.txt
38784STD-BV8_volume_readme.txt
38784STD-BV8_verstat_readme.txt
38784STD-BV8_acronym_readme.txt
38784STD-BV8a_index_readme.txt
```

### Functions documented from the filenames and readmes

- Acronym list generation from SGML acronym, term, and definition tags.
- Alphabetical index generation from primary and secondary index tags.
- Numerical index generation for IPB style part number and figure/index data.
- Reference designator index generation.
- SSSN index generation.
- Combined reference designator and SSSN index generation.
- List of Effective Pages generation, including volume level LEP handling.
- Table footnote and split table processing using page break output from composition.
- MOTI output instance generation using include/ignore marked sections.
- Verification status matter replacement using `vsmatter.dat` style data.

### Representative generated outputs

```text
filename.ext.acrm
index.sgml
<dss>_index.sgml
<dss>_index.ps
<dss>_index_after_change.sgml
<dss>_index_after_change.ps
numindxlist.out
numindx_final.sgml
refdes_final.sgml
sssn_final.sgml
refdes_sssn_final.sgml
final.sgml
vollep1.out
vollep2.out
<dss>_table.sgml
<dss>_table.ps
table.sgml
vsmatter.dat
vsmatter.out
```

## `7700H-CV9D0P0_scripts.zip`

This script package supports MIL-DTL-7700 style flight manual and checklist processing.

### File inventory

```text
7700G-CV6D0P0_remove_labels.xom
7700checklistExtract.xom
7700G-CV6D0P0_contents1.xom
7700G-CV6D0P0_contents2.xom
7700checklistExtract.sh
7700G-CV6D0P0_secttoc.sh
7700G-CV6D0P0_removelabels.sh
7700H-CV9D0P0_sectcontents.sh
7700H-CV9D0P0_sectcontents5x9.sh
7700H-CV9D0P0_sectcontents5x11.sh
```

### Functions documented from the filenames and readmes

- Extract checklist content from a flight manual SGML instance.
- Generate section tables of contents.
- Remove page break labels from intermediate SGML output.
- Handle standard, 5x9, and 5x11 composition variants.
- Compose once to get page break data, generate section content, then compose again for final output.

### Representative generated outputs

```text
final.sgml
final.ps
contents1.out
contents2.out
first.omni.inputs
second.omni.inputs
```

## `9977L-GV9D0P0_scripts.zip`

This is a small script package for MIL-DTL-9977 Appendix G style processing.

### File inventory

```text
9977L-GV9D0P0_mcarnum.txt
9977L-GV8aD0P0_mcarnum1.xom
9977L-GV8aD0P0_mcarnum2.xom
9977L-GV9D0P0_mcarnum.sh
```

### Functions documented from the filenames and readme

- Place multiple carriage number values into page footers.
- Use task and multiple carriage number footer elements.
- Run DLComposer more than once because pagination changes can change footer placement.
- Produce final SGML and composed PostScript output.

### Representative generated outputs

```text
mcarnum1.out
mcarnum2.out
mcarnum3.out
final.sgml
final.ps
```

## SGML elements seen in the script logic

The OmniMark programs process technical manual tags such as:

```text
<acronym>
<term>
<def>
<prindex>
<secindex>
<pgbrk>
<partno>
<ipbfigureno>
<ipbfigindex>
<ipbrefdes>
<ipbsssn>
<table>
<tgroup>
<tfndisplay>
<task>
<mcarnumfooter>
<mcarnumitem>
```

## Converter impact

No code path in this repository currently consumes OmniMark `.xom`, shell `.sh`, SGML `.sgml`, FOSI `.fosi`, or DTD `.dtd` files. They are documented for future triage only.

Potential future work:

1. Detect SGML and TMSS script packages in uploaded ZIP or self extracting EXE packages.
2. Report them in the package scan output rather than trying to convert them as images.
3. Treat `.sgml`, `.sgm`, `.xom`, `.fosi`, `.dtd`, `.ps`, `.out`, `.acrm`, `.dat`, and `.inputs` as technical data package context files.
4. Keep C4/MIL image conversion separate from SGML/XML technical manual rendering.

## Summary

These script packages document a legacy technical order publishing pipeline:

```text
SGML technical order source
  -> OmniMark .xom transformations
  -> generated SGML/intermediate files
  -> DLComposer + FOSI composition
  -> PostScript/PDF style output
```

They should not be added to the active C4 raster conversion flow unless a future feature explicitly handles SGML/TMSS package inventory or technical manual rendering.
