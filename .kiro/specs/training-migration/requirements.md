# Requirements Document

## Introduction
Migrate the /training page from FastHTML to Next.js. The page displays training videos (primarily RuTube embeds) organized by dynamic categories. Admin users can create, edit, and delete videos. All authenticated users can view.

## Requirements

### Requirement 1: Training Video Grid
**Objective:** As a user, I want to browse training videos in a visual grid, so that I can find and watch relevant content.

#### Acceptance Criteria
1. The Training Page shall display videos in a responsive grid (1 col mobile, 2 tablet, 3 desktop).
2. Each video card shall show an embedded player (16:9 aspect ratio), title, description (2-line clamp), and category badge.
3. The Training Page shall support RuTube embeds (including private videos with tokens) and YouTube embeds.
4. When no videos exist, the Training Page shall show an empty state with guidance.

### Requirement 2: Category Filtering
**Objective:** As a user, I want to filter videos by category, so that I can find content relevant to my role.

#### Acceptance Criteria
1. The Training Page shall display category tabs populated from distinct categories in the database.
2. The Training Page shall include an "Все" (All) tab as the default showing all videos.
3. When a user selects a category tab, the Training Page shall filter to show only videos in that category.
4. The active category shall persist in URL query params (?category=value).

### Requirement 3: Admin CRUD
**Objective:** As an admin, I want to add, edit, and delete training videos, so that I can manage educational content.

#### Acceptance Criteria
1. Where the user has admin role, the Training Page shall display an "Добавить видео" button.
2. When admin clicks "Добавить видео", the Training Page shall open a dialog with fields: URL, title, category, description.
3. The create dialog shall auto-detect platform (RuTube/YouTube) from the pasted URL.
4. Where the user has admin role, each video card shall show edit and delete action buttons.
5. The edit dialog shall pre-fill all fields with current values.
6. The delete dialog shall require confirmation before removing the video.
7. While the user lacks admin role, the Training Page shall not display any CRUD controls.
