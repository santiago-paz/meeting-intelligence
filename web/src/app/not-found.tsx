import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6">
      <Empty className="border py-12">
        <EmptyHeader>
          <EmptyTitle className="text-base">That page doesn’t exist</EmptyTitle>
          <EmptyDescription>It may have been removed, or the link is wrong.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild variant="outline">
            <Link href="/">Back to meetings</Link>
          </Button>
        </EmptyContent>
      </Empty>
    </main>
  );
}
