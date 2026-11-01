import {
  useSortable,
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import { DocumentState, Page, renderUrl } from "./api";
function Thumbnail({
  doc,
  page,
  active,
  selected,
  onSelect,
}: {
  doc: DocumentState;
  page: Page;
  active: boolean;
  selected: boolean;
  onSelect: (page: Page, multi: boolean) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: page.id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`thumbnail ${active ? "active" : ""}`}
    >
      <button
        className="drag-handle"
        title="Drag to reorder; Space then arrow keys with keyboard"
        {...attributes}
        {...listeners}
      >
        <GripVertical size={14} />
      </button>
      <button
        className="thumb-page"
        onClick={(e) => onSelect(page, e.ctrlKey || e.metaKey || e.shiftKey)}
        aria-label={`Page ${page.number}`}
        aria-current={active ? "page" : undefined}
      >
        <img
          loading="lazy"
          src={renderUrl(doc, page, 0.2)}
          alt={`Preview of page ${page.number}`}
        />
        <span>{page.number}</span>
      </button>
      <input
        type="checkbox"
        aria-label={`Select page ${page.number}`}
        checked={selected}
        onChange={() => onSelect(page, true)}
      />
    </div>
  );
}
export default function Thumbnails({
  doc,
  active,
  selected,
  onSelect,
  onReorder,
}: {
  doc: DocumentState;
  active: string;
  selected: string[];
  onSelect: (p: Page, multi: boolean) => void;
  onReorder: (ids: string[]) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={({ active, over }) => {
        if (over && active.id !== over.id) {
          const ids = doc.pages.map((p) => p.id);
          onReorder(
            arrayMove(
              ids,
              ids.indexOf(String(active.id)),
              ids.indexOf(String(over.id)),
            ),
          );
        }
      }}
    >
      <SortableContext
        items={doc.pages.map((p) => p.id)}
        strategy={verticalListSortingStrategy}
      >
        {doc.pages.map((p) => (
          <Thumbnail
            key={p.id}
            doc={doc}
            page={p}
            active={p.id === active}
            selected={selected.includes(p.id)}
            onSelect={onSelect}
          />
        ))}
      </SortableContext>
    </DndContext>
  );
}
