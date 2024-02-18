import Link from "next/link";

export default function NotFound() {
    return (
        <div className="w-96 mx-auto py-20">
            <h2 className="font-title text-4xl">Nothing here!</h2>
            <p>
                Backtrack to the last split in the dungeon and try another path.
            </p>
            <Link href="/">Return Home</Link>
        </div>
    );
}
