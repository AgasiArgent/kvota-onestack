"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Video } from "lucide-react";
import { Toaster } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { TrainingVideo } from "@/entities/training-video/types";
import { getEmbedUrl } from "@/entities/training-video/types";
import { CreateVideoDialog } from "./create-video-dialog";
import { EditVideoDialog } from "./edit-video-dialog";
import { DeleteVideoDialog } from "./delete-video-dialog";
import { VideoCard } from "./video-card";

interface TrainingPageProps {
  videos: TrainingVideo[];
  categories: string[];
  activeCategory: string;
  isAdmin: boolean;
  orgId: string;
  userId: string;
}

export function TrainingPage({
  videos,
  categories,
  activeCategory,
  isAdmin,
  orgId,
  userId,
}: TrainingPageProps) {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const [editVideo, setEditVideo] = useState<TrainingVideo | null>(null);
  const [deleteVideo, setDeleteVideo] = useState<TrainingVideo | null>(null);

  function handleCategoryClick(category: string) {
    if (category === "") {
      router.push("/training");
    } else {
      router.push(`/training?category=${encodeURIComponent(category)}`);
    }
  }

  return (
    <div className="space-y-6">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Обучение</h1>
        {isAdmin && (
          <Button
            size="sm"
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={() => setCreateOpen(true)}
          >
            <Plus size={16} />
            Добавить видео
          </Button>
        )}
      </div>

      {/* Category tabs */}
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => handleCategoryClick("")}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              activeCategory === ""
                ? "bg-accent text-white"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            }`}
          >
            Все
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => handleCategoryClick(cat)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                activeCategory === cat
                  ? "bg-accent text-white"
                  : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Video grid */}
      {videos.length > 0 ? (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              embedUrl={getEmbedUrl(video.youtube_id, video.platform)}
              isAdmin={isAdmin}
              onEdit={() => setEditVideo(video)}
              onDelete={() => setDeleteVideo(video)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Video size={48} className="text-muted-foreground mb-4" />
          <p className="text-lg font-medium text-muted-foreground">
            Нет обучающих видео
          </p>
          {isAdmin && (
            <p className="text-sm text-muted-foreground mt-1">
              Нажмите &laquo;Добавить видео&raquo;, чтобы загрузить первое видео
            </p>
          )}
        </div>
      )}

      {/* CRUD Dialogs */}
      {isAdmin && (
        <>
          <CreateVideoDialog
            open={createOpen}
            onOpenChange={setCreateOpen}
            orgId={orgId}
            userId={userId}
            existingCategories={categories}
          />
          <EditVideoDialog
            video={editVideo}
            onClose={() => setEditVideo(null)}
            existingCategories={categories}
          />
          <DeleteVideoDialog
            video={deleteVideo}
            onClose={() => setDeleteVideo(null)}
          />
        </>
      )}
    </div>
  );
}
