# Third-party sources

- shadcn/ui: https://github.com/shadcn-ui/ui — official registry files in src/components/ui, MIT, full license in SHADCN_LICENSE.txt. Imports adjusted to the project's cn utility; application tokens and Korean UI copy applied.
- Aceternity UI Multi Step Loader: https://ui.aceternity.com/components/multi-step-loader — step layout followed in src/agent/ScanLoader.tsx (own implementation). Licensing: https://ui.aceternity.com/licence
- Magic UI: MAGIC_UI_LICENSE.txt is kept from an earlier version that used its Animated Beam. The current screen does not include Magic UI source.
- Pretendard v1.3.9: https://github.com/orioncactus/pretendard — Kil Hyung-jin. SIL Open Font License, full license in public/fonts/OFL.txt.
- OpenStreetMap tiles and data attribution is displayed on the map. https://www.openstreetmap.org/copyright
- Leaflet, React, Radix UI, Motion, Lucide and Tabler are installed through npm; their license notices remain in the installed packages and package-lock.json records exact versions.

## Satoshi (FontShare) — 저장소에는 포함하지 않음

- 출처: https://www.fontshare.com/fonts/satoshi (Indian Type Foundry), ITF Free Font License
- 화면은 숫자 표시에만 씀(`Satoshi-500/700/900.woff2`). 공개 저장소 재배포 범위가 불분명해 파일은 넣지 않음
- 없으면 숫자도 Pretendard로 표시됨. 같은 모양이 필요하면 FontShare에서 받아 `public/fonts/`에 둠
