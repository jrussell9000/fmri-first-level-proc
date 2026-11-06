# Schaefer 400 + Tian S4 atlas

The parcellation `abcd/` staging passes to `rest_conn` and the n-back analyses as `--atlas`, in
the BOLD's own space, MNI152NLin2009cAsym at 2 mm.

| File | What it is |
|---|---|
| `Schaefer2018_400Parcels_7Networks_order_Tian_Subcortex_S4_3T_MNI152NLin2009cAsym_2mm.nii.gz` | The atlas: 454 parcels |
| `Schaefer2018_400Parcels_7Networks_order_Tian_Subcortex_S4_label.txt` | Each parcel's name, value and colour |
| `LICENSE-Tian-Melbourne-Subcortex-Atlas.txt` | The Melbourne Subcortex Atlas licence |
| `LICENSE-CBIG-Schaefer2018.md` | CBIG's MIT licence, which covers the Schaefer parcellation |

**Parcel order.** Values 1–54 are Tian's subcortical parcels and 55–454 are Schaefer's 400 cortical
parcels, in the 7-network order. So in any parcel-by-parcel output, the subcortex comes first.

## Source

Both files are copied unchanged from
[yetianmed/subcortex](https://github.com/yetianmed/subcortex) at commit
`dcad93421ea8021d6c5738df0a915a2223cd82aa`:
- `Group-Parcellation/3T/Cortex-Subcortex/MNIvolumetric/Schaefer2018_400Parcels_7Networks_order_Tian_Subcortex_S4_3T_MNI152NLin2009cAsym_2mm.nii.gz`;
- `Group-Parcellation/3T/Cortex-Subcortex/Schaefer2018_400Parcels_7Networks_order_Tian_Subcortex_S4_label.txt`.

The atlas's SHA-256 is `b105e68db7b716885c11cb80fc4fc147bc14d117a39850a34936fddee70728f6`. It
matches the copy cloudpipe ships.

`LICENSE-CBIG-Schaefer2018.md` is
[ThomasYeoLab/CBIG](https://github.com/ThomasYeoLab/CBIG)'s `LICENSE.md` at commit
`634f676630929a71297852d01dd92a287103e861`.

## Licences and citation

The subcortical parcels are under the Melbourne Subcortex Atlas licence. It allows use, copying,
modification, publication and distribution, on condition that any publication using the atlas
cites Tian et al. (2020). The cortical parcels come from CBIG's Schaefer parcellation, under the MIT
licence, whose notice must accompany copies.

Cite both when you publish results that use this atlas:

- Schaefer, A., Kong, R., Gordon, E. M., Laumann, T. O., Zuo, X.-N., Holmes, A. J., Eickhoff, S. B.,
  & Yeo, B. T. T. (2018). Local-global parcellation of the human cerebral cortex from intrinsic
  functional connectivity MRI. *Cerebral Cortex*, 28(9), 3095–3114.
  https://doi.org/10.1093/cercor/bhx179
- Tian, Y., Margulies, D. S., Breakspear, M., & Zalesky, A. (2020). Topographic organization of the
  human subcortex unveiled with functional connectivity gradients. *Nature Neuroscience*, 23(11),
  1421–1432. https://doi.org/10.1038/s41593-020-00711-6
