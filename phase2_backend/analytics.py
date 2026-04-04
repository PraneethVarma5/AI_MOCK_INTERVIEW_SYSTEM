"""
analytics.py file — Performance analytics routes.
Returns chart-ready data for the frontend dashboard.
"""
from fastapi import APIRouter, HTTPException, Request
from supabase_client import get_supabase_admin

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_user_id_from_token(request: Request) -> str | None:
    """Extract user ID from Authorization header."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    if not token:
        return None
    try:
        from supabase_client import get_supabase
        sb = get_supabase()
        user = sb.auth.get_user(token)
        return str(user.user.id) if user and user.user else None
    except Exception:
        return None


@router.get("/dashboard")
async def get_dashboard(request: Request):
    """
    Returns all analytics data needed for the performance dashboard:
    - overall stats (total sessions, avg score, best score, improvement %)
    - score over time (line chart)
    - performance by question type (bar chart)
    - recent sessions (table)
    - score distribution (histogram)
    - weak areas (based on low-scoring question types/topics)
    """
    user_id = _get_user_id_from_token(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    sb = get_supabase_admin()

    try:
        # ── Completed sessions ──────────────────────────────────────────────
        sessions_res = sb.table("sessions") \
            .select("id, mode, role, difficulty, experience_level, overall_score, created_at, completed_at, num_questions") \
            .eq("user_id", user_id) \
            .eq("status", "completed") \
            .order("created_at", desc=False) \
            .execute()

        sessions = sessions_res.data or []

        # ── All answers for this user ────────────────────────────────────────
        if sessions:
            session_ids = [s["id"] for s in sessions]
            answers_res = sb.table("session_answers") \
                .select("session_id, question_type, question_difficulty, score, question_text") \
                .in_("session_id", session_ids) \
                .execute()
            answers = answers_res.data or []
        else:
            answers = []

        # ── Compute overall stats ────────────────────────────────────────────
        total_sessions = len(sessions)
        scores = [s["overall_score"] for s in sessions if s["overall_score"] is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        best_score = round(max(scores), 1) if scores else 0

        # Improvement: compare first 3 sessions avg vs last 3 sessions avg
        improvement = 0.0
        if len(scores) >= 4:
            first_avg = sum(scores[:3]) / 3
            last_avg = sum(scores[-3:]) / 3
            improvement = round(last_avg - first_avg, 1)

        total_questions = len(answers)
        strong_answers = sum(1 for a in answers if a.get("score", 0) >= 7)
        weak_answers = sum(1 for a in answers if a.get("score", 0) is not None and a.get("score", 0) < 5)

        # ── Score over time (line chart data) ───────────────────────────────
        score_over_time = []
        for i, s in enumerate(sessions, 1):
            if s["overall_score"] is not None:
                score_over_time.append({
                    "session_number": i,
                    "score": round(s["overall_score"], 1),
                    "mode": s["mode"],
                    "date": s["created_at"][:10] if s["created_at"] else "",
                    "role": s.get("role", "")
                })

        # ── Performance by question type (bar chart) ─────────────────────────
        type_stats = {}
        for a in answers:
            t = a.get("question_type") or "general"
            if t not in type_stats:
                type_stats[t] = {"scores": [], "count": 0}
            if a.get("score") is not None:
                type_stats[t]["scores"].append(a["score"])
                type_stats[t]["count"] += 1

        by_type = []
        for t, data in type_stats.items():
            avg = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else 0
            by_type.append({
                "type": t.capitalize(),
                "avg_score": avg,
                "count": data["count"],
                "strong": sum(1 for s in data["scores"] if s >= 7),
                "weak": sum(1 for s in data["scores"] if s < 5)
            })

        # ── Performance by difficulty ─────────────────────────────────────────
        diff_stats = {}
        for a in answers:
            d = a.get("question_difficulty") or "medium"
            if d not in diff_stats:
                diff_stats[d] = []
            if a.get("score") is not None:
                diff_stats[d].append(a["score"])

        by_difficulty = []
        for d, sc in diff_stats.items():
            by_difficulty.append({
                "difficulty": d.capitalize(),
                "avg_score": round(sum(sc) / len(sc), 1) if sc else 0,
                "count": len(sc)
            })

        # ── Mode distribution (donut chart) ──────────────────────────────────
        mode_counts = {}
        for s in sessions:
            m = s.get("mode", "unknown")
            mode_counts[m] = mode_counts.get(m, 0) + 1

        mode_distribution = [{"mode": k.upper(), "count": v} for k, v in mode_counts.items()]
                # ── Average score by mode ────────────────────────────────────────────
        mode_score_stats = {}
        for s in sessions:
            mode = s.get("mode", "unknown")
            score = s.get("overall_score")
            if score is None:
                continue
            if mode not in mode_score_stats:
                mode_score_stats[mode] = []
            mode_score_stats[mode].append(score)

        mode_avg_scores = []
        for mode, scs in mode_score_stats.items():
            mode_avg_scores.append({
                "mode": mode.upper(),
                "avg_score": round(sum(scs) / len(scs), 1),
                "count": len(scs)
            })

        # ── Score trend by mode ───────────────────────────────────────────────
        score_over_time_by_mode = {}
        for i, s in enumerate(sessions, 1):
            score = s.get("overall_score")
            mode = s.get("mode", "unknown")
            if score is None:
                continue

            if mode not in score_over_time_by_mode:
                score_over_time_by_mode[mode] = []

            score_over_time_by_mode[mode].append({
                "session_number": i,
                "score": round(score, 1),
                "date": s["created_at"][:10] if s.get("created_at") else "",
                "role": s.get("role", "")
            })

        # ── Score distribution (histogram) ───────────────────────────────────
        buckets = {"0-3": 0, "4-5": 0, "6-7": 0, "8-9": 0, "10": 0}
        all_scores = [a.get("score", 0) for a in answers if a.get("score") is not None]
        for sc in all_scores:
            if sc <= 3:
                buckets["0-3"] += 1
            elif sc <= 5:
                buckets["4-5"] += 1
            elif sc <= 7:
                buckets["6-7"] += 1
            elif sc < 10:
                buckets["8-9"] += 1
            else:
                buckets["10"] += 1

        score_distribution = [{"range": k, "count": v} for k, v in buckets.items()]

        # ── Recent sessions (table) ───────────────────────────────────────────
        recent = []
        for s in reversed(sessions[-10:]):
            recent.append({
                "id": s["id"],
                "mode": s.get("mode", ""),
                "role": s.get("role", ""),
                "score": s.get("overall_score"),
                "questions": s.get("num_questions", 0),
                "difficulty": s.get("difficulty", ""),
                "date": s.get("created_at", "")[:10] if s.get("created_at") else ""
            })
        recent.reverse()

        # ── Weak areas (topics with avg score < 6) ────────────────────────────
        weak_areas = [t for t in by_type if t["avg_score"] < 6 and t["count"] >= 2]
        weak_areas.sort(key=lambda x: x["avg_score"])

        return {
            "overview": {
                "total_sessions": total_sessions,
                "avg_score": avg_score,
                "best_score": best_score,
                "improvement": improvement,
                "total_questions": total_questions,
                "strong_answers": strong_answers,
                "weak_answers": weak_answers,
                "strong_rate": round(strong_answers / total_questions * 100, 1) if total_questions else 0
            },
            "score_over_time": score_over_time,
            "by_type": by_type,
            "by_difficulty": by_difficulty,
            "mode_distribution": mode_distribution,
            "mode_avg_scores": mode_avg_scores,
            "score_over_time_by_mode": score_over_time_by_mode,
            "score_distribution": score_distribution,
            "recent_sessions": recent,
            "weak_areas": weak_areas[:3]
        }

    except Exception as e:
        print(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")


@router.get("/session/{session_id}")
async def get_session_detail(session_id: str, request: Request):
    """Return detailed breakdown for a single session."""
    user_id = _get_user_id_from_token(request)
    sb = get_supabase_admin()

    try:
        session_res = sb.table("sessions") \
            .select("*") \
            .eq("id", session_id) \
            .single() \
            .execute()

        if not session_res.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = session_res.data

        # Security: only owner or guest (null user_id) can see
        if session.get("user_id") and session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        answers_res = sb.table("session_answers") \
            .select("*") \
            .eq("session_id", session_id) \
            .order("question_index") \
            .execute()

        return {
            "session": session,
            "answers": answers_res.data or []
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))