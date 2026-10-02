export function WorkspacePlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="mx-auto max-w-7xl p-5 lg:p-9">
      <div className="rounded-[28px] bg-white p-7 shadow-[0_18px_45px_rgba(30,39,70,.09)] lg:p-9">
        <p className="text-sm font-semibold text-slate-500">Workspace</p>
        <h1 className="mt-2 text-2xl font-bold">{title}</h1>
        <p className="mt-3 max-w-2xl text-slate-600">{description}</p>
        <p className="mt-6 inline-flex rounded-full bg-[var(--yellow)] px-3 py-1 text-xs font-semibold">
          Feature in progress
        </p>
      </div>
    </section>
  );
}