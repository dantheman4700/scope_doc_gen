import { Skeleton } from "@/components/ui/skeleton";

export function ProjectsListSkeleton() {
  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto">
      <div className="card">
        <div className="flex justify-between items-start gap-6">
          <div className="flex-1">
            <Skeleton className="h-8 w-32 mb-2" />
            <Skeleton className="h-4 w-64" />
          </div>
          <Skeleton className="h-10 w-28" />
        </div>
      </div>

      <div className="card p-0">
        <div className="p-4 border-b border-border">
          <Skeleton className="h-9 w-48" />
        </div>
        <div className="p-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 py-3 border-b border-border last:border-0">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-48 flex-1" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function RunDetailSkeleton() {
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <Skeleton className="h-4 w-64 mb-6" />
      
      <div className="card">
        <div className="mb-6">
          <Skeleton className="h-8 w-48 mb-2" />
          <div className="flex gap-2 mb-2">
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-5 w-24" />
          </div>
          <Skeleton className="h-4 w-80" />
        </div>

        <div className="flex gap-3 mb-6 pb-6 border-b border-border">
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-9 w-40" />
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-36" />
        </div>

        <div className="space-y-6">
          <div>
            <Skeleton className="h-6 w-32 mb-4" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-5/6" />
            </div>
          </div>

          <div>
            <Skeleton className="h-6 w-44 mb-4" />
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-20 w-full rounded-md" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SettingsSkeleton() {
  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="card mb-6">
        <Skeleton className="h-8 w-40 mb-4" />
        <div className="space-y-4">
          <div>
            <Skeleton className="h-4 w-24 mb-2" />
            <Skeleton className="h-10 w-full" />
          </div>
          <div>
            <Skeleton className="h-4 w-32 mb-2" />
            <Skeleton className="h-10 w-full" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>
      </div>

      <div className="card">
        <Skeleton className="h-8 w-36 mb-4" />
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i}>
              <Skeleton className="h-4 w-28 mb-2" />
              <Skeleton className="h-10 w-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr>
      {[...Array(columns)].map((_, i) => (
        <td key={i} className="py-3 px-4">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  );
}

export function CardSkeleton() {
  return (
    <div className="card">
      <Skeleton className="h-6 w-32 mb-3" />
      <Skeleton className="h-4 w-full mb-2" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

