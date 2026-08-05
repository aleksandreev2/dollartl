export type Title = {
  id: string;
  slug: string;
  english_title: string;
  original_title: string;
  original_language: string;
  description: string;
  publication_status: string;
  boosty_url?: string | null;
  is_published: boolean;
  latest_chapter: number;
  updated_at: string;
  aliases: string[];
  release_count: number;
};

export type Release = {
  id: string;
  title_id?: string;
  chapter_start: number;
  chapter_end: number;
  chapter_label: string;
  display_name?: string | null;
  boosty_url?: string | null;
  is_published: boolean;
  comments_enabled: boolean;
  validation_status: string;
  validation_message?: string | null;
  updated_at: string;
};

export type Revision = {
  id: string;
  revision: number;
  reason: string;
  created_at: string;
  snapshot?: Record<string, unknown>;
};

export type FileVersion = {
  id: string;
  file_kind: string;
  version: number;
  filename: string;
  size_bytes: number;
  sha256: string;
  is_active: boolean;
  created_at: string;
};

export type TitlePage = {
  page: number;
  pages: number;
  total: number;
  items: Title[];
};

export type TitleDetail = {
  title: Title;
  cover_url?: string | null;
  releases: Release[];
  revisions: Revision[];
};

export type ReleaseDetail = {
  release: Release;
  title?: { english_title: string } | null;
  files: FileVersion[];
  revisions: Revision[];
};

export type Preview = {
  bot_html: string;
  channel_html: string;
  warnings: string[];
};

export type CleanupPreview = {
  candidate_count: number;
  bytes: number;
  confirmation: string;
  items: Array<{
    id: string;
    filename: string;
    version: number;
    size_bytes: number;
    created_at: string;
  }>;
};

export type FailedPublication = {
  id: string;
  target_type: string;
  target_id: string;
  error?: string | null;
  updated_at: string;
};

export type PipelineDetection = {
  chapter_start: number | null;
  chapter_end: number | null;
  source: string;
  confidence: string;
  observed_chapters: number[];
  note?: string | null;
};

export type PipelineAnalysis = {
  suggested: {
    english_title: string;
    original_title: string;
    original_language: string;
    translation_language: string;
    publication_status: string;
    description: string;
    source_url: string;
    boosty_url: string;
    aliases: string[];
    chapter_start: number | null;
    chapter_end: number | null;
    chapter_count: number | null;
    display_name: string;
  };
  confidence: string;
  warnings: string[];
  files: Array<{
    kind: "pdf" | "epub";
    filename: string;
    title?: string | null;
    language?: string | null;
    text_language?: string | null;
    description?: string | null;
    creator?: string | null;
    chapter_detection: PipelineDetection;
  }>;
  possible_duplicates: Array<{
    id: string;
    english_title: string;
    original_title: string;
    slug: string;
  }>;
};

export type ReasonAction = {
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  run: (reason: string) => Promise<void>;
};

export type DataState<T> = {
  data: T | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
};

export type CatalogModal =
  | { kind: "create-release"; title: Title }
  | { kind: "edit-title"; title: Title }
  | { kind: "edit-release"; release: Release }
  | { kind: "preview"; title: string; data: Preview }
  | { kind: "cleanup"; data: CleanupPreview; key: string }
  | { kind: "reason"; action: ReasonAction }
  | null;
