import LandingGamesList from "./Landing/LandingGamesList";

export default function Landing() {
    return (
        <>
            <div className="bg-[url('/images/landing_top_bg.jpg')] bg-bottom bg-cover">
                <div className="max-w-screen-xl mx-auto">
                    <h1 className="text-white text-3xl font-bold text-center md:text-left mb-2 pt-4 md:indent-16">
                        Scratch that RPG itch
                    </h1>
                    <h2 className="text-white text-lg mx-3 pb-4 text-center md:text-left md:indent-24">
                        Talk and play{" "}
                        <span className="font-semibold">RPGs</span> with{" "}
                        <span className="font-semibold">
                            hundreds of players
                        </span>
                        !
                    </h2>
                    <LandingGamesList />
                </div>
            </div>
        </>
    );
}
