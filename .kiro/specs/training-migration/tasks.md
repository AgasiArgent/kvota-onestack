# Implementation Plan

- [x] 1. Training video entity layer
- [x] 1.1 Define types, URL parser, and embed URL generator
  - TrainingVideo and TrainingVideoFormData interfaces
  - parseVideoUrl() for RuTube (public + private with token) and YouTube
  - getEmbedUrl() generating correct iframe src
  - _Requirements: 1.2, 1.3_

- [x] 1.2 Implement server-side queries
  - fetchTrainingVideos(orgId, category?) with creator name join
  - fetchCategories(orgId) returning distinct sorted categories
  - _Requirements: 1.1, 2.1_

- [x] 1.3 Implement client-side mutations
  - createTrainingVideo, updateTrainingVideo, deleteTrainingVideo
  - URL parsing integrated into create/update
  - _Requirements: 3.2, 3.5, 3.6_

- [x] 2. Training page and UI components
- [x] 2.1 Build training page server component
  - Auth, parallel data fetch, admin role detection
  - _Requirements: 1.1, 2.1, 3.1_

- [x] 2.2 Build video grid with category tabs
  - Responsive grid (1/2/3 cols), category pill tabs, empty state
  - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 2.3 Build video card component
  - 16:9 iframe embed, title, description clamp, category badge, admin hover actions
  - _Requirements: 1.2, 1.3, 3.4_

- [x] 2.4 Build CRUD dialogs (admin only)
  - Create dialog with URL auto-detect, edit dialog pre-filled, delete confirmation
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_
