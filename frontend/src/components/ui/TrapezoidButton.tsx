import { agency_fb } from "@/app/util";
import { classMerge } from "@/lib/utils";
import { ReactNode } from "react";

export default function TrapezoidButton({
    className = "",
    children,
}: {
    className?: string;
    children: ReactNode;
}) {
    let classes = classMerge(
        `trapezoid text-white text-3xl ${agency_fb.className}`,
        className
    );

    return (
        <button type="button" className={classes}>
            <div className="px-3 py-1">{children}</div>
        </button>
    );
}
